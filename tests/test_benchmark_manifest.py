from pathlib import Path

import pytest

from khalkha_frontend.benchmark import (
    AudioTake,
    BenchmarkManifest,
    ManualRating,
    ValidationError,
    derive_traffic_light,
    load_audio_takes,
    load_benchmark,
    load_ratings,
    validate_related,
)
from scripts.mn.validate_benchmark import display_path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks" / "MN-PHON-250" / "manifest.yaml"


def test_real_manifest_preserves_contiguous_250_items() -> None:
    manifest = load_benchmark(MANIFEST)
    assert len(manifest.items) == 250
    assert [item.id for item in manifest.items] == [f"MNPHON_{i:03d}" for i in range(1, 251)]
    assert all(item.expected_phoneme is None and item.expected_phone is None for item in manifest.items)


def test_metadata_derivation_is_literal_only() -> None:
    manifest = load_benchmark(MANIFEST)
    assert manifest.items[0].target_grapheme == "л"
    assert manifest.items[0].context == "CV"
    assert manifest.items[0].position == "initial"
    assert manifest.items[0].left_context is None
    assert manifest.items[0].right_context == "а"
    assert manifest.items[7].target_grapheme == "л"
    assert manifest.items[7].position == "final"
    assert manifest.items[7].left_context == "а"
    assert manifest.items[190].target_grapheme == "ь"
    assert manifest.items[190].position == "final"
    assert manifest.items[210].target_grapheme is None
    assert manifest.items[210].context == "Ci"
    assert manifest.items[154].target_grapheme == "х"
    assert manifest.items[154].left_context is None
    assert manifest.items[154].right_context is None


def test_expected_value_requires_evidence() -> None:
    raw = {
        "schema_version": 2,
        "benchmark": {"item_count": 250},
        "items": [
            {
                "id": f"MNPHON_{i:03d}",
                "number": i,
                "text": "а",
                "target_group": "L",
                "legacy_category": "carrier_CV",
                "lexicality": "carrier",
                "expected_phoneme": "x" if i == 1 else None,
                "expected_phone": None,
                "evidence": [],
            }
            for i in range(1, 251)
        ],
    }
    with pytest.raises(ValidationError, match="expected phoneme"):
        BenchmarkManifest.from_mapping(raw)
    raw["items"][0]["evidence"] = [{"id": "synthetic", "source": "fixture", "kind": "synthetic"}]
    with pytest.raises(ValidationError, match="evidence kind"):
        BenchmarkManifest.from_mapping(raw)


def test_audio_path_and_score_invariants() -> None:
    with pytest.raises(ValidationError, match="data/raw/music3"):
        AudioTake.from_mapping(
            {
                "id": "take",
                "item_id": "MNPHON_001",
                "source": "music3",
                "run_id": "a",
                "path": "outside/file.wav",
            },
            0,
        )
    legacy_prefix = "_" * 2 + "GET" + "_" * 2
    with pytest.raises(ValidationError, match="marker"):
        AudioTake.from_mapping(
            {
                "id": "take",
                "item_id": "MNPHON_001",
                "source": "native_speech",
                "run_id": "a",
                "path": f"data/raw/native_speech/{legacy_prefix}speech/file.wav",
            },
            0,
        )
    with pytest.raises(ValidationError, match="native_speech"):
        AudioTake.from_mapping(
            {
                "id": "take",
                "item_id": "MNPHON_001",
                "source": "native_speech",
                "run_id": "a",
                "path": "data/raw/music3/file.wav",
            },
            0,
        )
    with pytest.raises(ValidationError, match="score"):
        ManualRating.from_mapping(
            {
                "id": "rating-bad-score",
                "item_id": "MNPHON_001",
                "audio_take_id": "take",
                "score": 3,
                "rater_pseudonym": "r1",
                "timestamp": "2026-08-15T00:00:00Z",
            },
            0,
        )
    with pytest.raises(ValidationError, match=r"ratings\[0\]\.id"):
        ManualRating.from_mapping(
            {
                "item_id": "MNPHON_001",
                "audio_take_id": "take",
                "score": 2,
                "rater_pseudonym": "r1",
                "timestamp": "2026-08-15T00:00:00Z",
            },
            0,
        )


def test_empty_related_manifests_validate() -> None:
    manifest = load_benchmark(MANIFEST)
    assert load_audio_takes(MANIFEST.with_name("audio_manifest.yaml")) == ()
    assert load_ratings(MANIFEST.with_name("evaluations.yaml")) == ()
    assert validate_related(manifest) == []


def test_rating_item_must_match_audio_take_item() -> None:
    manifest = load_benchmark(MANIFEST)
    take = AudioTake.from_mapping(
        {
            "id": "MNPHON_001_native_speech_a",
            "item_id": "MNPHON_001",
            "source": "native_speech",
            "run_id": "a",
            "path": "data/raw/native_speech/MN-PHON-250/one.wav",
        },
        0,
    )
    rating = ManualRating.from_mapping(
        {
            "id": "rating-1",
            "item_id": "MNPHON_002",
            "audio_take_id": take.id,
            "score": 2,
            "rater_pseudonym": "r1",
            "timestamp": "2026-08-15T00:00:00Z",
        },
        0,
    )
    with pytest.raises(ValidationError, match="disagrees"):
        validate_related(manifest, (take,), (rating,))


def test_repeated_rater_does_not_satisfy_minimum_count() -> None:
    ratings = tuple(
        ManualRating.from_mapping(
            {
                "id": f"rating-{i}",
                "item_id": "MNPHON_001",
                "audio_take_id": "take",
                "score": 2,
                "rater_pseudonym": "same-rater",
                "timestamp": f"2026-08-15T00:0{i}:00Z",
            },
            i,
        )
        for i in range(2)
    )
    assert derive_traffic_light(ratings, min_count=2) == "NEEDS_REVIEW"
    with pytest.raises(ValueError, match="min_count"):
        derive_traffic_light(ratings, min_count=0)


def test_direct_take_and_rating_construction_enforces_invariants() -> None:
    with pytest.raises(ValidationError, match="data/raw/music3"):
        AudioTake("take", "MNPHON_001", "music3", "a", "data/raw/native_speech/x.wav")
    with pytest.raises(ValidationError, match="score"):
        ManualRating("rating", "MNPHON_001", "take", 4, "r1", "2026-08-15")


def test_report_path_does_not_leak_absolute_home_path(tmp_path: Path) -> None:
    outside = tmp_path / "manifest.yaml"
    displayed = display_path(outside, ROOT)
    assert displayed == outside.name
    assert str(tmp_path) not in displayed
