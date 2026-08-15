"""Fail-closed runtime and accelerator preflight.

The preflight is intentionally independent of model imports.  Callers should
run it before constructing a model so an unavailable or undersized accelerator
cannot turn into an unbounded CPU load.  It only probes runtime and filesystem
metadata; it never allocates a model or downloads an artifact.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import torch


class PreflightBlocked(RuntimeError):
    """Raised when the requested runtime policy cannot be satisfied."""


def _gib(value: int | float | None) -> float | None:
    if value is None:
        return None
    return round(float(value) / (1024**3), 3)


def _sanitized_text(value: object) -> str:
    """Remove user/home paths from text that may be persisted in a report."""
    text = str(value)
    replacements = {
        str(Path.home()): "<HOME>",
        os.environ.get("USERPROFILE", ""): "<HOME>",
        os.environ.get("HOMEDRIVE", "") + os.environ.get("HOMEPATH", ""): "<HOME>",
    }
    for source, target in replacements.items():
        if source:
            text = text.replace(source, target)
    return text


def _dtype_name(dtype: str | torch.dtype) -> str:
    if isinstance(dtype, torch.dtype):
        return str(dtype).removeprefix("torch.")
    value = str(dtype).strip().lower()
    aliases = {"fp16": "float16", "fp32": "float32", "bf16": "bfloat16"}
    return aliases.get(value, value)


@dataclass(frozen=True)
class PreflightPolicy:
    require_cuda: bool = False
    allow_cpu: bool = False
    requested_dtype: str = "float16"
    requested_device: str = "auto"
    min_free_vram_gib: float | None = None
    min_free_storage_gib: float | None = None


@dataclass(frozen=True)
class PreflightResult:
    status: str
    device: str | None
    policy: dict[str, Any]
    environment: dict[str, Any]
    storage: dict[str, Any]
    devices: list[dict[str, Any]]
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _probe_cuda(torch_module: Any) -> tuple[list[dict[str, Any]], list[str]]:
    devices: list[dict[str, Any]] = []
    warnings: list[str] = []
    try:
        count = int(torch_module.cuda.device_count()) if torch_module.cuda.is_available() else 0
    except Exception as exc:  # pragma: no cover - defensive for broken drivers
        warnings.append(f"CUDA probe failed: {_sanitized_text(exc)}")
        count = 0
    for index in range(count):
        info: dict[str, Any] = {"index": index}
        try:
            props = torch_module.cuda.get_device_properties(index)
            info.update(
                {
                    "name": _sanitized_text(getattr(props, "name", "unknown")),
                    "compute_capability": [int(props.major), int(props.minor)],
                    "total_vram_gib": _gib(getattr(props, "total_memory", None)),
                }
            )
        except Exception as exc:  # pragma: no cover - defensive for broken drivers
            info["probe_error"] = _sanitized_text(exc)
        try:
            free, total = torch_module.cuda.mem_get_info(index)
            info.update({"free_vram_gib": _gib(free), "runtime_total_vram_gib": _gib(total)})
        except Exception as exc:  # pragma: no cover - defensive for broken drivers
            info["memory_probe_error"] = _sanitized_text(exc)
        devices.append(info)
    return devices, warnings


def _storage_probe(path: Path, disk_usage: Callable[[str], Any]) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    try:
        usage = disk_usage(str(resolved))
        return {
            "path_label": "workspace",
            "free_gib": _gib(usage.free),
            "total_gib": _gib(usage.total),
        }
    except (FileNotFoundError, OSError) as exc:
        return {"path_label": "workspace", "probe_error": _sanitized_text(exc)}


def run_preflight(
    *,
    policy: PreflightPolicy,
    workspace: Path | str = ".",
    checkpoint_dir: Path | str | None = None,
    torch_module: Any = torch,
    disk_usage: Callable[[str], Any] = shutil.disk_usage,
) -> PreflightResult:
    """Probe runtime state and apply an explicit fail-closed device policy."""

    dtype = _dtype_name(policy.requested_dtype)
    requested_device = str(policy.requested_device).strip().lower()
    valid_dtypes = {"float16", "bfloat16", "float32"}
    errors: list[str] = []
    warnings: list[str] = []
    if dtype not in valid_dtypes:
        errors.append(f"unsupported requested dtype: {dtype}")

    try:
        cuda_available = bool(torch_module.cuda.is_available())
        cuda_version = getattr(torch_module.version, "cuda", None)
        torch_version = str(torch_module.__version__)
    except Exception as exc:  # pragma: no cover - defensive for import/runtime failures
        cuda_available = False
        cuda_version = None
        torch_version = "unknown"
        errors.append(f"PyTorch runtime probe failed: {_sanitized_text(exc)}")

    devices, probe_warnings = _probe_cuda(torch_module)
    warnings.extend(probe_warnings)
    storage = _storage_probe(Path(workspace), disk_usage)
    storage_targets = [("workspace", storage)]
    if checkpoint_dir is not None:
        checkpoint_storage = _storage_probe(Path(checkpoint_dir), disk_usage)
        checkpoint_storage["path_label"] = "checkpoint"
        storage["checkpoint"] = checkpoint_storage
        storage_targets.append(("checkpoint", checkpoint_storage))
    for label, target in storage_targets:
        if "probe_error" in target:
            errors.append(f"{label} storage could not be probed")
        elif policy.min_free_storage_gib is not None and target.get("free_gib", 0) < policy.min_free_storage_gib:
            errors.append(
                f"insufficient {label} storage: "
                f"{target.get('free_gib')} GiB free, "
                f"{policy.min_free_storage_gib} GiB required"
            )

    if policy.require_cuda and policy.allow_cpu:
        errors.append("--require-cuda and --allow-cpu are mutually exclusive")
    if requested_device == "auto":
        requested_device = "cuda:0" if cuda_available or policy.require_cuda else "cpu"
    if requested_device == "cpu":
        device = "cpu"
        if policy.require_cuda:
            errors.append("CUDA is required but CPU was requested")
        if not policy.allow_cpu:
            errors.append("CPU execution requires explicit --allow-cpu opt-in")
    elif requested_device == "cuda" or requested_device.startswith("cuda:"):
        try:
            device_index = 0 if requested_device == "cuda" else int(requested_device.split(":", 1)[1])
        except ValueError:
            device_index = -1
        device = f"cuda:{device_index}" if device_index >= 0 else None
        if not cuda_available:
            errors.append("CUDA is required but no CUDA runtime/device is available")
        elif device_index < 0 or device_index >= len(devices):
            errors.append(f"requested CUDA device is not visible: {requested_device}")
        elif policy.min_free_vram_gib is not None:
            free_vram = devices[device_index].get("free_vram_gib")
            if free_vram is None:
                errors.append(f"free VRAM could not be measured for {device}")
            elif free_vram < policy.min_free_vram_gib:
                errors.append(
                    f"insufficient free VRAM on {device}: {free_vram} GiB free, "
                    f"{policy.min_free_vram_gib} GiB required"
                )
    else:
        device = None
        errors.append(f"unsupported requested device: {requested_device}")

    environment = {
        "python": platform.python_version(),
        "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
        "torch": torch_version,
        "cuda_build": cuda_version,
        "cuda_available": cuda_available,
        "visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", "<default>"),
        "requested_dtype": dtype,
    }
    return PreflightResult(
        status="ready" if not errors else "blocked_environment",
        device=device if not errors else None,
        policy={**asdict(policy), "requested_dtype": dtype},
        environment=environment,
        storage=storage,
        devices=devices,
        errors=[_sanitized_text(error) for error in errors],
        warnings=[_sanitized_text(warning) for warning in warnings],
    )


def write_report(result: PreflightResult, output_path: Path | str) -> None:
    """Write a sanitized, deterministic JSON report to *output_path*."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
