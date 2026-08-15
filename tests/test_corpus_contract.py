# flake8: noqa: E501
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from vocalrender.corpus import CorpusError, generate_splits, validate_manifest, verify_splits


def _item(root: Path, index: int, **overrides):
    audio = root / f"audio-{index}.flac"
    score = root / f"score-{index}.json"
    audio.write_bytes(f"audio-{index}".encode())
    score.write_text("{}", encoding="utf-8")
    item = {
        "id": f"item-{index}",
        "source_id": "approved-corpus",
        "audio_path": audio.relative_to(root).as_posix(),
        "score_path": score.relative_to(root).as_posix(),
        "audio_sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
        "score_sha256": hashlib.sha256(score.read_bytes()).hexdigest(),
        "duration_seconds": 4.0,
        "language": "mn",
        "variety": "standard_khalkha",
        "vocal_type": "singing",
        "singer_group": f"singer-{index}",
        "song_group": f"song-{index}",
        "session_group": f"session-{index}",
        "consent_ref": f"consent-{index}",
        "license": {"identifier": "research-license"},
        "redistribution": "allowed",
        "research_evaluation_use": "allowed",
        "training_use": "allowed",
        "derivative_model_permission": "allowed",
        "review_status": "approved",
    }
    item.update(overrides)
    return item


def _write_manifest(root: Path, items):
    path = root / "data" / "manifests" / "mn_svs" / "corpus.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump({"schema_version": 1, "items": items}), encoding="utf-8")
    return path


def test_unknown_rights_are_excluded_fail_closed(tmp_path: Path):
    item = _item(tmp_path, 1, training_use="unknown")
    report = validate_manifest(_write_manifest(tmp_path, [item]), repository_root=tmp_path)
    assert not report.eligible
    assert "rights_training_use_not_allowed" in report.excluded_reasons


def test_pii_is_rejected_from_manifest(tmp_path: Path):
    item = _item(tmp_path, 1, singer_name="not allowed")
    with pytest.raises(CorpusError, match="personal-data"):
        validate_manifest(_write_manifest(tmp_path, [item]), repository_root=tmp_path)


def test_path_traversal_is_excluded(tmp_path: Path):
    item = _item(tmp_path, 1, audio_path="../outside.flac")
    report = validate_manifest(_write_manifest(tmp_path, [item]), repository_root=tmp_path)
    assert not report.eligible
    assert any(reason.startswith("invalid:") for reason in report.excluded_reasons)


def test_grouped_split_is_deterministic_and_disjoint(tmp_path: Path):
    items = [_item(tmp_path, index) for index in range(12)]
    manifest = _write_manifest(tmp_path, items)
    report = validate_manifest(manifest, repository_root=tmp_path)
    first = generate_splits(report, manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
    second = generate_splits(report, manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
    assert first == second
    verify_splits(report, first)


def test_prompt_target_overlap_is_rejected(tmp_path: Path):
    item = _item(
        tmp_path,
        1,
        target_interval={"start_seconds": 0, "end_seconds": 2},
        prompt={"start_seconds": 1, "end_seconds": 3},
    )
    report = validate_manifest(_write_manifest(tmp_path, [item]), repository_root=tmp_path)
    assert any("prompt-target intervals overlap" in error for error in report.errors)
    with pytest.raises(CorpusError, match="prompt-target intervals overlap"):
        generate_splits(report, manifest_sha256="a" * 64)


def test_diagnostic_sources_are_never_eligible(tmp_path: Path):
    item = _item(tmp_path, 1, source_id="MN-PHON-32")
    report = validate_manifest(_write_manifest(tmp_path, [item]), repository_root=tmp_path)
    assert not report.eligible
    assert "excluded_source" in report.excluded_reasons
