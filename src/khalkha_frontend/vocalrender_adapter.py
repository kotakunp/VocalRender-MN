"""Strict, score-preserving conversion at the VocalRender boundary.

This module is the only Khalkha frontend component that queries VocalRender's
score token maps. The import is lazy and token-map-only; no model, tokenizer,
checkpoint, or inference path is loaded. Pronunciation information remains in
the ``mn_frontend`` sidecar because the released prompt path consumes raw
lyric strings, not explicit phones.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from functools import lru_cache
from math import isfinite
from pathlib import Path
from typing import Any, Mapping, Sequence

from .normalize import normalize_text
from .types import (
    EvidenceRef,
    KhalkhaScore,
    LyricScoreUnit,
    PronunciationUnit,
    ScoreNote as _ScoreNote,
    TextIssue,
    VocalRenderScoreEntry,
)

__all__ = [
    "KhalkhaScore",
    "LyricScoreUnit",
    "ScoreAdapterError",
    "ScoreNote",
    "from_vocalrender_entry",
    "to_vocalrender_entry",
    "validate_vocalrender_entry",
]


_SILENCE_MARKERS = frozenset({"AP", "SP", "<REST>"})


class ScoreAdapterError(ValueError):
    """Raised when score data would be ambiguous or rejected upstream."""


class ScoreNote(_ScoreNote):
    """ScoreNote with canonical upstream note-token validation at the boundary."""

    def __post_init__(self) -> None:
        super().__post_init__()
        note_tokens, _ = _upstream_token_maps()
        if self.note_value not in note_tokens:
            raise ScoreAdapterError(f"unsupported VocalRender note token: {self.note_value!r}")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_silence_marker(text: str) -> bool:
    return text.upper() in _SILENCE_MARKERS


@lru_cache(maxsize=1)
def _upstream_token_maps() -> tuple[frozenset[str], frozenset[int]]:
    """Load canonical note tokens and BPM values without loading a model."""

    try:
        from vocalrender.model.svs_utils import get_svs_token_maps

        _, note_tokens, bpm_tokens, _, _ = get_svs_token_maps()
    except Exception as exc:  # pragma: no cover - depends on installed upstream deps
        raise ScoreAdapterError("cannot query VocalRender score token maps; refusing unsafe defaults") from exc
    bpm_values = frozenset(
        int(token.removeprefix("<BPM_").removesuffix(">"))
        for token in bpm_tokens
        if token.startswith("<BPM_") and token.endswith(">")
    )
    return frozenset(note_tokens), bpm_values


def _jsonable(value: Any, path: str = "metadata") -> Any:
    """Convert frozen frontend values to JSON-compatible values or fail closed."""

    if isinstance(value, float) and not isfinite(value):
        raise ScoreAdapterError(f"{path} contains a non-finite number")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (EvidenceRef,)):
        return {
            "id": value.stable_id,
            "source_kind": value.source_kind,
            "citation_or_path": value.citation_or_path,
            "item_id": value.item_id,
            "note": value.note,
            "reviewer": value.reviewer,
            "status": value.status,
            "date": value.date,
        }
    if isinstance(value, TextIssue):
        return _jsonable(asdict(value), path)
    if is_dataclass(value):
        return _jsonable(asdict(value), path)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ScoreAdapterError(f"{path} contains a non-string mapping key")
            result[key] = _jsonable(item, f"{path}.{key}")
        return result
    if isinstance(value, (tuple, list)):
        return [_jsonable(item, f"{path}[]") for item in value]
    if isinstance(value, (set, frozenset)):
        return [_jsonable(item, f"{path}[]") for item in sorted(value, key=repr)]
    if isinstance(value, Path):
        return value.as_posix()
    raise ScoreAdapterError(f"{path} contains unsupported value type {type(value).__name__}")


def _pronunciation_sidecar(value: PronunciationUnit | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "orthographic_text": value.orthographic_text,
        "status": value.status.value,
        "phonemic_symbols": list(value.phonemic_symbols) if value.phonemic_symbols is not None else None,
        "surface_phones": list(value.surface_phones) if value.surface_phones is not None else None,
        "evidence_refs": [_jsonable(ref) for ref in value.evidence_refs],
        "manual_override": value.manual_override,
    }


def _validate_item_name(value: Any, path: str = "item_name") -> None:
    if not isinstance(value, str) or not value.strip():
        raise ScoreAdapterError(f"{path} must be a nonempty string")
    if value != value.strip():
        raise ScoreAdapterError(f"{path} must not contain surrounding whitespace")
    if any(separator in value for separator in ("/", "\\", "\x00")) or value.strip() in {".", ".."}:
        raise ScoreAdapterError(f"{path} must be metadata, not a file path")


def _validate_word(value: Any, index: int) -> None:
    path = f"word[{index}]"
    if not isinstance(value, str) or not value.strip():
        raise ScoreAdapterError(f"{path} must be nonempty text")
    if value != value.strip():
        raise ScoreAdapterError(f"{path} must not contain surrounding whitespace")


def _validate_score(score: KhalkhaScore) -> tuple[tuple[str, ...], tuple[Any, ...]]:
    note_tokens, bpm_values = _upstream_token_maps()
    if score.bpm not in bpm_values or not 1 <= score.bpm <= 255:
        raise ScoreAdapterError(f"bpm={score.bpm} is outside VocalRender's supported 1..255 range")
    _validate_item_name(score.item_name)
    words: list[str] = []
    flattened: list[tuple[int, ScoreNote, LyricScoreUnit]] = []
    for unit_index, unit in enumerate(score.units):
        if _is_silence_marker(unit.text):
            text = unit.text.upper() if unit.text.upper() != "<REST>" else "<REST>"
        else:
            normalized = normalize_text(unit.text)
            text = normalized.normalized
            if not text:
                raise ScoreAdapterError(f"units[{unit_index}].text normalizes to empty text")
        words.append(text)
        for note_index, note in enumerate(unit.notes):
            if note.note_value not in note_tokens:
                raise ScoreAdapterError(
                    f"units[{unit_index}].notes[{note_index}].note_value={note.note_value!r} "
                    "is not in VocalRender's supported note-token map"
                )
            if note.midi_pitch == 0 and not _is_silence_marker(text):
                raise ScoreAdapterError(
                    f"units[{unit_index}].notes[{note_index}].midi_pitch=0 requires AP, SP, or <REST> text"
                )
            if note.midi_pitch != 0 and _is_silence_marker(text):
                raise ScoreAdapterError(f"units[{unit_index}].notes[{note_index}] silence marker must use midi_pitch=0")
            flattened.append((unit_index, note, unit))
    return tuple(words), tuple(flattened)


def to_vocalrender_entry(score: KhalkhaScore) -> dict[str, Any]:
    """Flatten an explicitly aligned score into validated upstream JSON."""

    if not isinstance(score, KhalkhaScore):
        raise TypeError("score must be a KhalkhaScore")
    words, flattened = _validate_score(score)
    pitches = tuple(note.midi_pitch for _, note, _ in flattened)
    notes = tuple(note.note_value for _, note, _ in flattened)
    pitch2word = tuple(unit_index for unit_index, _, _ in flattened)
    sidecar_units: list[dict[str, Any]] = []
    for index, (unit, word) in enumerate(zip(score.units, words)):
        normalized = normalize_text(unit.text) if not _is_silence_marker(unit.text) else None
        sidecar_units.append(
            {
                "index": index,
                "text": word,
                "source_span": list(unit.source_span) if unit.source_span is not None else None,
                "normalization": {
                    "original": unit.text,
                    "normalized": word,
                    "issues": [_jsonable(issue) for issue in (normalized.issues if normalized else ())],
                },
                "pronunciation": _pronunciation_sidecar(unit.pronunciation),
            }
        )
    sidecar = {
        "schema_version": 1,
        "prompt_audio": score.prompt_audio,
        "metadata": _jsonable(score.metadata),
        "units": sidecar_units,
    }
    entry = VocalRenderScoreEntry(
        word=words,
        pitch=pitches,
        note=notes,
        pitch2word=pitch2word,
        bpm=score.bpm,
        item_name=score.item_name,
        mn_frontend=sidecar,
    )
    result = {
        "word": list(entry.word),
        "pitch": list(entry.pitch),
        "note": list(entry.note),
        "pitch2word": list(entry.pitch2word),
        "bpm": entry.bpm,
        "item_name": entry.item_name,
        "mn_frontend": _jsonable(entry.mn_frontend),
    }
    validate_vocalrender_entry(result)
    return result


def _sequence(value: Any, path: str) -> list[Any]:
    if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Sequence):
        raise ScoreAdapterError(f"{path} must be an array")
    return list(value)


def validate_vocalrender_entry(entry: Mapping[str, Any]) -> None:
    """Validate an existing upstream score entry before prompt construction."""

    if not isinstance(entry, Mapping):
        raise TypeError("entry must be a mapping")
    required = ("word", "pitch", "note", "pitch2word", "bpm")
    missing = [field for field in required if field not in entry]
    if missing:
        raise ScoreAdapterError(f"missing required entry fields: {missing!r}")
    words = _sequence(entry["word"], "word")
    pitches = _sequence(entry["pitch"], "pitch")
    notes = _sequence(entry["note"], "note")
    mappings = _sequence(entry["pitch2word"], "pitch2word")
    if not words:
        raise ScoreAdapterError("word must contain at least one lyric unit")
    if not pitches or not notes or not mappings:
        raise ScoreAdapterError("pitch, note, and pitch2word must be nonempty")
    if not len(pitches) == len(notes) == len(mappings):
        raise ScoreAdapterError("pitch, note, and pitch2word must have equal lengths")
    note_tokens, bpm_values = _upstream_token_maps()
    bpm = entry["bpm"]
    if not _is_int(bpm) or bpm not in bpm_values or not 1 <= bpm <= 255:
        raise ScoreAdapterError("bpm must be an integer in the supported 1..255 range")
    for index, word in enumerate(words):
        _validate_word(word, index)
    referenced: set[int] = set()
    previous = -1
    for index, (pitch, note, mapping) in enumerate(zip(pitches, notes, mappings)):
        if not _is_int(pitch) or not 0 <= pitch <= 127:
            raise ScoreAdapterError(f"pitch[{index}] must be an integer in 0..127")
        if not isinstance(note, str) or note not in note_tokens:
            raise ScoreAdapterError(f"note[{index}]={note!r} is not supported")
        if not _is_int(mapping) or not 0 <= mapping < len(words):
            raise ScoreAdapterError(f"pitch2word[{index}] is outside word range")
        if mapping < previous:
            raise ScoreAdapterError("pitch2word must be nondecreasing")
        previous = mapping
        referenced.add(mapping)
        if pitch == 0 and not _is_silence_marker(words[mapping]):
            raise ScoreAdapterError(f"pitch[{index}]=0 requires an AP, SP, or <REST> word")
        if pitch != 0 and _is_silence_marker(words[mapping]):
            raise ScoreAdapterError(f"silence word at pitch[{index}] requires pitch 0")
    for index, word in enumerate(words):
        if index not in referenced and not _is_silence_marker(word):
            raise ScoreAdapterError(f"word[{index}] is not referenced by pitch2word")
    if "item_name" in entry and entry["item_name"] is not None:
        _validate_item_name(entry["item_name"])
    if "mn_frontend" in entry and not isinstance(entry["mn_frontend"], Mapping):
        raise ScoreAdapterError("mn_frontend must be a mapping when supplied")
    _validate_optional_durations(entry, "word_dur", len(words))
    _validate_optional_durations(entry, "pitch_dur", len(pitches))


def _validate_optional_durations(entry: Mapping[str, Any], field: str, expected_length: int) -> None:
    if field not in entry:
        return
    values = _sequence(entry[field], field)
    if len(values) != expected_length:
        raise ScoreAdapterError(f"{field} must contain {expected_length} values")
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
            raise ScoreAdapterError(f"{field}[{index}] must be a nonnegative number")


def from_vocalrender_entry(entry: Mapping[str, Any]) -> KhalkhaScore:
    """Reconstruct the supported neutral core fields from a validated entry.

    Unit-level pronunciation and normalization details remain authoritative in
    ``mn_frontend`` and are not promoted into model-consumed score fields.
    """

    validate_vocalrender_entry(entry)
    if entry.get("item_name") is None:
        raise ScoreAdapterError("item_name is required for neutral score conversion")
    words = list(entry["word"])
    grouped: list[list[ScoreNote]] = [[] for _ in words]
    for pitch, note, mapping in zip(entry["pitch"], entry["note"], entry["pitch2word"]):
        grouped[mapping].append(ScoreNote(pitch, note))
    if any(not notes for notes in grouped):
        raise ScoreAdapterError("neutral conversion cannot omit an unreferenced lyric unit")
    units = tuple(LyricScoreUnit(text, tuple(notes)) for text, notes in zip(words, grouped))
    sidecar = entry.get("mn_frontend") or {}
    if not isinstance(sidecar, Mapping):
        raise ScoreAdapterError("mn_frontend must be a mapping")
    metadata = sidecar.get("metadata", {})
    prompt_audio = sidecar.get("prompt_audio")
    return KhalkhaScore(
        units=units,
        bpm=entry["bpm"],
        item_name=entry["item_name"],
        prompt_audio=prompt_audio,
        metadata=metadata if isinstance(metadata, Mapping) else {},
    )
