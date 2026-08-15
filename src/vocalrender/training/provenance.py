"""Immutable, fail-closed provenance records for local training runs."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import uuid
from copy import deepcopy
from pathlib import Path

import torch


def _canonical_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_records(root: Path, *, recursive: bool) -> list[dict]:
    if not root.is_dir():
        return []
    candidates = root.rglob("*") if recursive else root.glob("*")
    allowed_suffixes = {
        ".arrow",
        ".bin",
        ".ckpt",
        ".json",
        ".model",
        ".pth",
        ".safetensors",
        ".txt",
        ".yaml",
        ".yml",
    }
    records = []
    for path in sorted(p for p in candidates if p.is_file()):
        if path.suffix.lower() not in allowed_suffixes:
            continue
        records.append(
            {
                "file": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return records


def _source_control_record() -> dict:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, check=True, text=True).stdout.strip()
        patch = subprocess.run(["git", "diff", "--binary", "HEAD"], capture_output=True, check=True).stdout
        return {"git_sha": commit, "dirty_patch_sha256": hashlib.sha256(patch).hexdigest()}
    except (OSError, subprocess.SubprocessError):
        return {"git_sha": "unavailable", "dirty_patch_sha256": "unavailable"}


def build_run_manifest(config, *, world_size: int) -> dict:
    config_payload = config.to_dict()
    compatibility = deepcopy(config_payload)
    for alias in ("total_steps", "num_iters", "max_steps"):
        compatibility.get("train", {}).pop(alias, None)
    base_root = Path(config.model.pretrained_path)
    data_root = Path(config.data.preprocessed_data_path)
    stable = {
        "schema_version": 1,
        "config": config_payload,
        "compatibility_sha256": hashlib.sha256(_canonical_bytes(compatibility)).hexdigest(),
        "base_model": {
            "identifier": base_root.name,
            "artifacts": _artifact_records(base_root, recursive=False),
        },
        "dataset": {
            "identifier": data_root.name,
            "manifests": _artifact_records(data_root, recursive=True),
        },
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda_runtime": torch.version.cuda,
            "world_size": int(world_size),
        },
        "source_control": _source_control_record(),
    }
    stable["run_id"] = hashlib.sha256(_canonical_bytes(stable)).hexdigest()
    return stable


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def ensure_run_manifest(save_dir: Path, config, *, world_size: int) -> dict:
    """Create an immutable manifest or verify a compatible intentional resume."""
    save_dir.mkdir(parents=True, exist_ok=True)
    current = build_run_manifest(config, world_size=world_size)
    path = save_dir / "run_manifest.json"
    if not path.exists():
        _atomic_json(path, current)
        return current
    with path.open("r", encoding="utf-8") as handle:
        stored = json.load(handle)
    if stored.get("compatibility_sha256") != current["compatibility_sha256"]:
        raise ValueError("Training configuration is incompatible with the existing run manifest")
    for field in ("base_model", "dataset", "runtime", "source_control"):
        if stored.get(field) != current.get(field):
            raise ValueError(f"Training provenance changed for {field}; refusing unsafe resume")
    previous_steps = int(stored["config"]["train"]["total_steps"])
    if int(config.train.total_steps) < previous_steps:
        raise ValueError("train.total_steps cannot be reduced when resuming an existing run")
    return stored


def update_run_status(save_dir: Path, *, status: str, step: int | None = None, detail: str = "") -> None:
    payload = {"schema_version": 1, "status": status}
    if step is not None:
        payload["step"] = int(step)
    if detail:
        payload["detail"] = str(detail)[:500]
    _atomic_json(save_dir / "run_status.json", payload)
