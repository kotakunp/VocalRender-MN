import json
from pathlib import Path

import pytest

from vocalrender.training.checkpoint import (
    CHECKPOINT_MANIFEST,
    _publish_latest_pointer,
    _write_checkpoint_manifest,
    resolve_latest_checkpoint,
    verify_checkpoint,
)


def _published_checkpoint(root: Path, tag: str, payload: bytes = b"weights") -> Path:
    folder = root / tag
    folder.mkdir()
    (folder / "model.safetensors").write_bytes(payload)
    _write_checkpoint_manifest(folder, step=1, tag=tag)
    return folder


def test_manifest_detects_corruption_and_extra_files(tmp_path):
    folder = _published_checkpoint(tmp_path, "step_0000001")
    verify_checkpoint(folder)

    (folder / "model.safetensors").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="mismatch"):
        verify_checkpoint(folder)

    folder = _published_checkpoint(tmp_path, "step_0000002")
    (folder / "unexpected.bin").write_bytes(b"extra")
    with pytest.raises(ValueError, match="file set"):
        verify_checkpoint(folder)


def test_latest_pointer_is_verified_and_fail_closed(tmp_path):
    first = _published_checkpoint(tmp_path, "step_0000001")
    second = _published_checkpoint(tmp_path, "step_0000002", b"new")
    _publish_latest_pointer(tmp_path, first)
    assert resolve_latest_checkpoint(tmp_path) == first.resolve()

    _publish_latest_pointer(tmp_path, second)
    assert resolve_latest_checkpoint(tmp_path) == second.resolve()

    manifest = json.loads((second / CHECKPOINT_MANIFEST).read_text(encoding="utf-8"))
    manifest["step"] = 999
    (second / CHECKPOINT_MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest hash mismatch"):
        resolve_latest_checkpoint(tmp_path)


def test_latest_refuses_to_delete_legacy_real_directory(tmp_path):
    target = _published_checkpoint(tmp_path, "step_0000001")
    latest = tmp_path / "latest"
    latest.mkdir()
    (latest / "user-file").write_text("preserve", encoding="utf-8")
    with pytest.raises(ValueError, match="Refusing to replace"):
        _publish_latest_pointer(tmp_path, target)
    assert (latest / "user-file").read_text(encoding="utf-8") == "preserve"


def test_manifest_rejects_path_traversal_before_reading(tmp_path):
    folder = _published_checkpoint(tmp_path, "step_0000001")
    manifest_path = folder / CHECKPOINT_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["../outside.bin"] = {"size": 0, "sha256": "0" * 64}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe checkpoint manifest path"):
        verify_checkpoint(folder)
