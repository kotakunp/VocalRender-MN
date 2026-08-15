from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from vocalrender.runtime_preflight import PreflightPolicy, run_preflight


class _FakeCuda:
    def __init__(self, *, available: bool, devices: list[dict] | None = None):
        self._available = available
        self._devices = devices or []

    def is_available(self):
        return self._available

    def device_count(self):
        return len(self._devices)

    def get_device_properties(self, index):
        device = self._devices[index]
        return SimpleNamespace(
            name=device["name"],
            major=device["major"],
            minor=device["minor"],
            total_memory=device["total"],
        )

    def mem_get_info(self, index):
        device = self._devices[index]
        return device["free"], device["total"]


def _fake_torch(cuda):
    return SimpleNamespace(
        cuda=cuda,
        version=SimpleNamespace(cuda="12.8" if cuda._available else None),
        __version__="2.10.0+cu128" if cuda._available else "2.10.0+cpu",
    )


def _disk(free_gib):
    return lambda _: SimpleNamespace(free=int(free_gib * 1024**3), total=32 * 1024**3)


def test_no_cuda_is_blocked_without_explicit_cpu_opt_in(tmp_path: Path):
    result = run_preflight(
        policy=PreflightPolicy(require_cuda=True),
        workspace=tmp_path,
        torch_module=_fake_torch(_FakeCuda(available=False)),
        disk_usage=_disk(20),
    )

    assert result.status == "blocked_environment"
    assert result.device is None
    assert any("CUDA is required" in error for error in result.errors)


def test_cpu_requires_explicit_opt_in(tmp_path: Path):
    result = run_preflight(
        policy=PreflightPolicy(allow_cpu=True),
        workspace=tmp_path,
        torch_module=_fake_torch(_FakeCuda(available=False)),
        disk_usage=_disk(20),
    )

    assert result.ok
    assert result.device == "cpu"


def test_explicit_cpu_requires_opt_in_even_when_cuda_exists(tmp_path: Path):
    cuda = _FakeCuda(
        available=True,
        devices=[{"name": "GPU", "major": 8, "minor": 9, "free": 12 * 1024**3, "total": 12 * 1024**3}],
    )
    result = run_preflight(
        policy=PreflightPolicy(requested_device="cpu"),
        workspace=tmp_path,
        torch_module=_fake_torch(cuda),
        disk_usage=_disk(20),
    )
    assert not result.ok
    assert any("explicit --allow-cpu" in error for error in result.errors)


def test_requested_cuda_device_is_validated_not_best_visible_gpu(tmp_path: Path):
    cuda = _FakeCuda(
        available=True,
        devices=[
            {"name": "small", "major": 8, "minor": 6, "free": 4 * 1024**3, "total": 8 * 1024**3},
            {"name": "large", "major": 8, "minor": 9, "free": 20 * 1024**3, "total": 24 * 1024**3},
        ],
    )
    result = run_preflight(
        policy=PreflightPolicy(requested_device="cuda:0", min_free_vram_gib=10),
        workspace=tmp_path,
        torch_module=_fake_torch(cuda),
        disk_usage=_disk(20),
    )
    assert not result.ok
    assert "cuda:0" in result.errors[-1]


def test_insufficient_vram_and_storage_are_blocked(tmp_path: Path):
    cuda = _FakeCuda(
        available=True,
        devices=[{"name": "Test GPU", "major": 8, "minor": 9, "free": 8 * 1024**3, "total": 12 * 1024**3}],
    )
    result = run_preflight(
        policy=PreflightPolicy(min_free_vram_gib=10, min_free_storage_gib=20),
        workspace=tmp_path,
        torch_module=_fake_torch(cuda),
        disk_usage=_disk(4),
    )

    assert not result.ok
    assert any("VRAM" in error for error in result.errors)
    assert any("storage" in error for error in result.errors)


def test_valid_gpu_probe_reports_device_and_is_ready(tmp_path: Path):
    cuda = _FakeCuda(
        available=True,
        devices=[{"name": "Test GPU", "major": 8, "minor": 9, "free": 11 * 1024**3, "total": 12 * 1024**3}],
    )
    result = run_preflight(
        policy=PreflightPolicy(require_cuda=True, requested_dtype="bf16", min_free_vram_gib=10),
        workspace=tmp_path,
        torch_module=_fake_torch(cuda),
        disk_usage=_disk(20),
    )

    assert result.ok
    assert result.device == "cuda:0"
    assert result.policy["requested_dtype"] == "bfloat16"
    assert result.devices[0]["compute_capability"] == [8, 9]


def test_report_does_not_persist_workspace_path(tmp_path: Path):
    result = run_preflight(
        policy=PreflightPolicy(require_cuda=True),
        workspace=tmp_path,
        torch_module=_fake_torch(_FakeCuda(available=False)),
        disk_usage=_disk(20),
    )

    assert str(tmp_path) not in str(result.to_dict())


def test_checkpoint_storage_is_reported_and_gated(tmp_path: Path):
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    result = run_preflight(
        policy=PreflightPolicy(allow_cpu=True, min_free_storage_gib=10),
        workspace=tmp_path,
        checkpoint_dir=checkpoint,
        torch_module=_fake_torch(_FakeCuda(available=False)),
        disk_usage=_disk(20),
    )

    assert result.ok
    assert result.storage["checkpoint"]["path_label"] == "checkpoint"
    assert result.storage["checkpoint"]["free_gib"] == 20.0
