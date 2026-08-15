"""Contract tests for the score-preserving VocalRender adapter.

These tests intentionally exercise the neutral score boundary only.  They do
not load a checkpoint or invoke GPU/model code; the upstream regression uses
the small annotation helpers directly.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from khalkha_frontend.vocalrender_adapter import (
    KhalkhaScore,
    LyricScoreUnit,
    ScoreNote,
    from_vocalrender_entry,
    to_vocalrender_entry,
    validate_vocalrender_entry,
)
from khalkha_frontend.types import EvidenceRef, PronunciationUnit, ResolutionStatus

ROOT = Path(__file__).resolve().parents[1]
SCORE_FIXTURES = ROOT / "tests" / "fixtures" / "scores"
NOTE = "<NOTE_8>"


def _note(pitch: int = 60, note_value: str = NOTE) -> ScoreNote:
    return ScoreNote(midi_pitch=pitch, note_value=note_value)


def _unit(text: str = "би", *notes: ScoreNote, pronunciation=None) -> LyricScoreUnit:
    return LyricScoreUnit(text=text, notes=tuple(notes or (_note(),)), pronunciation=pronunciation)


def _score(
    *units: LyricScoreUnit,
    bpm: int = 96,
    item_name: str = "fixture",
    prompt_audio=None,
    metadata=None,
) -> KhalkhaScore:
    return KhalkhaScore(
        units=tuple(units),
        bpm=bpm,
        item_name=item_name,
        prompt_audio=prompt_audio,
        metadata={} if metadata is None else metadata,
    )


def _core(entry: dict) -> dict:
    return {key: entry[key] for key in ("item_name", "word", "pitch", "note", "pitch2word", "bpm")}


def _assert_rejected(factory) -> None:
    with pytest.raises((TypeError, ValueError, KeyError)):
        factory()


def _fixture_score() -> KhalkhaScore:
    raw = json.loads((SCORE_FIXTURES / "mn_score_input.json").read_text(encoding="utf-8"))
    units = []
    for raw_unit in raw["units"]:
        units.append(
            _unit(
                raw_unit["text"],
                *(_note(item["midi_pitch"], item["note_value"]) for item in raw_unit["notes"]),
            )
        )
    return _score(
        *units,
        bpm=raw["bpm"],
        item_name=raw["item_name"],
        prompt_audio=raw["prompt_audio"],
        metadata=raw["metadata"],
    )


def test_fixture_exact_shape_preserves_melisma_repeated_lyrics_and_ap_rest() -> None:
    expected = json.loads((SCORE_FIXTURES / "mn_score_expected_core.json").read_text(encoding="utf-8"))
    entry = to_vocalrender_entry(_fixture_score())

    assert _core(entry) == expected
    assert entry["mn_frontend"]["prompt_audio"] == "fixture_prompt.wav"
    assert set(entry) == {"item_name", "word", "pitch", "note", "pitch2word", "bpm", "mn_frontend"}
    assert entry["word"] == ["би", "хайр", "би", "AP"]
    assert entry["pitch2word"] == [0, 1, 1, 2, 3]
    assert entry["pitch"][-1] == 0


def test_checked_in_example_round_trips_to_exact_upstream_shape() -> None:
    source = json.loads((ROOT / "examples" / "mn_score_input.json").read_text(encoding="utf-8"))
    rendered = json.loads((ROOT / "examples" / "mn_vocalrender_score.json").read_text(encoding="utf-8"))
    assert isinstance(rendered, list) and len(rendered) == 1
    assert len(source["units"]) == 2
    assert rendered[0]["word"] == ["би", "хайр"]
    assert rendered[0]["pitch"] == [60, 64, 67]
    assert rendered[0]["pitch2word"] == [0, 0, 1]
    assert rendered[0]["mn_frontend"]["prompt_audio"] == "data/raw/native_speech/demo_prompt.wav"
    assert rendered[0]["mn_frontend"]["metadata"]["normalization_diagnostics"] == []
    validate_vocalrender_entry(rendered[0])


def test_sp_rest_uses_pitch_zero_but_regular_lyric_does_not() -> None:
    assert to_vocalrender_entry(_score(_unit("SP", _note(0))))["pitch"] == [0]
    _assert_rejected(lambda: to_vocalrender_entry(_score(_unit("би", _note(0)))))


def test_sidecar_is_namespaced_and_does_not_interfere_with_upstream_fields() -> None:
    plain = to_vocalrender_entry(_score(_unit("би", _note(60))))
    with_sidecar = to_vocalrender_entry(
        _score(
            _unit(
                "би",
                _note(60),
                pronunciation=PronunciationUnit(
                    orthographic_text="би",
                    phonemic_symbols=("p", "i"),
                    status=ResolutionStatus.RESOLVED,
                    evidence_refs=(
                        EvidenceRef(
                            stable_id="mn-test-001",
                            source_kind="manual_review",
                            citation_or_path="tests/fixtures/scores/mn_score_input.json",
                        ),
                    ),
                ),
            ),
            metadata={"nested": {"source": "synthetic"}},
        )
    )

    assert _core(with_sidecar) == _core(plain)
    assert "mn_frontend" in with_sidecar
    assert with_sidecar["mn_frontend"] != plain["mn_frontend"]
    assert "phoneme" not in with_sidecar
    assert "phone" not in with_sidecar
    assert "pronunciation" not in with_sidecar
    pronunciation = with_sidecar["mn_frontend"]["units"][0]["pronunciation"]
    assert pronunciation["status"] == "resolved"
    assert pronunciation["phonemic_symbols"] == ["p", "i"]
    assert pronunciation["evidence_refs"][0]["id"] == "mn-test-001"


def test_upstream_annotation_helpers_preserve_mapping_and_melisma_without_model() -> None:
    from vocalrender.training.svs_raw_data import convert_annotation_to_syllables, expand_syllables

    entry = to_vocalrender_entry(_score(_unit("би", _note(60)), _unit("хайр", _note(64), _note(67))))
    syllables = convert_annotation_to_syllables(entry["word"], entry["pitch"], entry["note"], entry["pitch2word"])
    assert syllables == [
        {"char": "би", "pitch": 60, "note": "<NOTE_8>"},
        {"char": "хайр", "pitch": [64, 67], "note": ["<NOTE_8>", "<NOTE_8>"]},
    ]
    expanded = expand_syllables(syllables)
    assert [row["word_idx"] for row in expanded] == [0, 1, 1]
    assert [row["char"] for row in expanded] == ["би", "хайр", "хайр"]


@pytest.mark.parametrize("pitch", [-1, 128, True, False])
def test_midi_pitch_boundaries_and_bool_rejection(pitch) -> None:
    _assert_rejected(lambda: ScoreNote(midi_pitch=pitch, note_value=NOTE))


@pytest.mark.parametrize("bpm", [-1, 0, 256, True, False])
def test_bpm_boundaries_zero_and_bool_rejection(bpm) -> None:
    _assert_rejected(lambda: _score(_unit("би", _note()), bpm=bpm))


@pytest.mark.parametrize("note_value", ["", None, True])
def test_invalid_note_value_types_fail_closed(note_value) -> None:
    _assert_rejected(lambda: ScoreNote(midi_pitch=60, note_value=note_value))


def test_unknown_well_formed_note_token_fails_at_upstream_boundary() -> None:
    _assert_rejected(lambda: _note(note_value="<NOTE_7>"))


def test_strict_nonempty_score_boundaries_and_safe_item_metadata() -> None:
    _assert_rejected(lambda: KhalkhaScore(units=(), bpm=96, item_name="empty"))
    _assert_rejected(lambda: LyricScoreUnit(text="", notes=(_note(),)))
    _assert_rejected(lambda: LyricScoreUnit(text="би", notes=()))
    _assert_rejected(lambda: KhalkhaScore(units=(_unit(),), bpm=96, item_name=""))
    _assert_rejected(lambda: KhalkhaScore(units=(_unit(),), bpm=96, item_name="folder/name"))


def test_missing_required_fields_have_no_silent_defaults() -> None:
    with pytest.raises(TypeError):
        ScoreNote(midi_pitch=60)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        LyricScoreUnit(text="би")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        KhalkhaScore(units=(_unit(),), item_name="missing-bpm")  # type: ignore[call-arg]


def test_immutable_score_is_deeply_immutable() -> None:
    score = _score(_unit("би", _note()), metadata={"nested": {"values": [1, 2]}})
    assert isinstance(score.units, tuple)
    assert isinstance(score.units[0].notes, tuple)
    with pytest.raises((AttributeError, TypeError)):
        score.bpm = 100  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        score.metadata["new"] = "value"  # type: ignore[index]
    with pytest.raises((AttributeError, TypeError)):
        score.metadata["nested"]["values"].append(3)  # type: ignore[index]
    with pytest.raises((AttributeError, TypeError)):
        score.units[0].notes += (_note(61),)  # type: ignore[misc]


def test_pronunciation_metadata_is_evidence_gated_and_typed() -> None:
    with pytest.raises(ValueError, match="evidence"):
        PronunciationUnit(orthographic_text="би", status=ResolutionStatus.RESOLVED)
    with pytest.raises(TypeError, match="PronunciationUnit"):
        _unit("би", pronunciation={"status": "resolved"})


def test_reverse_validation_accepts_sidecar_and_rejects_shape_errors() -> None:
    entry = to_vocalrender_entry(_score(_unit("хайр", _note(60), _note(64))))
    assert validate_vocalrender_entry(copy.deepcopy(entry)) is None

    no_sidecar = copy.deepcopy(entry)
    no_sidecar.pop("mn_frontend", None)
    assert validate_vocalrender_entry(no_sidecar) is None

    cases = []
    malformed = copy.deepcopy(entry)
    malformed["note"] = []
    cases.append(malformed)
    malformed = copy.deepcopy(entry)
    malformed["pitch2word"] = [True, 0]
    cases.append(malformed)
    malformed = copy.deepcopy(entry)
    malformed["pitch2word"] = [False, 0]
    cases.append(malformed)
    malformed = copy.deepcopy(entry)
    malformed["pitch2word"] = [1, 0]
    cases.append(malformed)
    malformed = copy.deepcopy(entry)
    malformed["pitch2word"] = [0, 2]
    cases.append(malformed)
    malformed = copy.deepcopy(entry)
    malformed["pitch"] = [60, 128]
    cases.append(malformed)
    malformed = copy.deepcopy(entry)
    malformed["bpm"] = 0
    cases.append(malformed)
    for candidate in cases:
        _assert_rejected(lambda candidate=candidate: validate_vocalrender_entry(candidate))


def test_reverse_validation_preserves_multi_character_units_without_splitting() -> None:
    entry = {
        "item_name": "multi",
        "word": ["хайр"],
        "pitch": [60],
        "note": [NOTE],
        "pitch2word": [0],
        "bpm": 96,
    }
    validate_vocalrender_entry(entry)
    assert entry["word"] == ["хайр"]


def test_supported_core_fields_round_trip_back_to_neutral_score() -> None:
    entry = to_vocalrender_entry(
        _score(
            _unit("би", _note(60)),
            _unit("хайр", _note(64), _note(67)),
            prompt_audio="prompt.wav",
            metadata={"source": "synthetic"},
        )
    )
    restored = from_vocalrender_entry(entry)
    rebuilt = to_vocalrender_entry(restored)
    assert _core(rebuilt) == _core(entry)
    assert rebuilt["mn_frontend"]["prompt_audio"] == "prompt.wav"
    assert rebuilt["mn_frontend"]["metadata"] == {"source": "synthetic"}


def test_reverse_validation_accepts_unrelated_upstream_metadata_and_checks_durations() -> None:
    entry = to_vocalrender_entry(_score(_unit("би", _note())))
    entry.update({"wav_fn": "ignored.wav", "word_dur": [0.5], "pitch_dur": [0.5]})
    validate_vocalrender_entry(entry)
    entry["pitch_dur"] = [float("nan")]
    _assert_rejected(lambda: validate_vocalrender_entry(entry))


def test_fixture_rejects_implicit_alignment_inputs() -> None:
    invalid = json.loads((SCORE_FIXTURES / "invalid_scores.json").read_text(encoding="utf-8"))
    assert "text" in invalid["full_text_without_alignment"]
    assert "units" not in invalid["full_text_without_alignment"]
    _assert_rejected(lambda: ScoreNote(**invalid["unsupported_note"]["units"][0]["notes"][0]))
    _assert_rejected(lambda: LyricScoreUnit(text="би", notes=()))


def test_cli_converts_example_and_refuses_implicit_alignment(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "mn" / "prepare_score.py"
    output = tmp_path / "score.json"
    completed = subprocess.run(
        [sys.executable, str(script), str(ROOT / "examples" / "mn_score_input.json"), "--output", str(output)],
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    assert json.loads(output.read_text(encoding="utf-8")) == json.loads(
        (ROOT / "examples" / "mn_vocalrender_score.json").read_text(encoding="utf-8")
    )

    ambiguous = tmp_path / "ambiguous.json"
    ambiguous.write_text(json.dumps({"item_name": "bad", "bpm": 96, "text": "би хайр"}), encoding="utf-8")
    rejected = subprocess.run(
        [sys.executable, str(script), str(ambiguous), "--output", "-"],
        check=False,
        capture_output=True,
    )
    assert rejected.returncode != 0
    assert b"explicit lyric-to-note alignment" in rejected.stderr


def test_cli_refuses_overwrite_without_force(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "mn" / "prepare_score.py"
    output = tmp_path / "existing.json"
    output.write_text("sentinel", encoding="utf-8")
    rejected = subprocess.run(
        [sys.executable, str(script), str(ROOT / "examples" / "mn_score_input.json"), "--output", str(output)],
        check=False,
        capture_output=True,
    )
    assert rejected.returncode != 0
    assert output.read_text(encoding="utf-8") == "sentinel"
