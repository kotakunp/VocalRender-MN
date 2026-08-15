"""Deterministic mining of orthographic contexts for research candidates.

All labels in this module describe literal Cyrillic adjacency.  They are
selectors for later human/linguistic review, never phone or IPA predictions.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, asdict
from pathlib import Path
import math
from typing import Iterable, Sequence

from .morphology import UniMorphKhalkha

# These sets are intentionally orthographic.  They are not a phoneme inventory.
MONGOLIAN_VOWELS = frozenset("аеёиоуүөыэюя")
MONGOLIAN_CONSONANTS = frozenset("бвгджзклмпрстфхцчшщъь") | frozenset("йқң")
FRONT_VOWELS = frozenset("эөүёе")
BACK_VOWELS = frozenset("аоуыюя")
SPECIAL_PROBE_CHARACTERS = tuple("ӨөҮүЁёЬьЪъ")


@dataclass(frozen=True)
class FrequencyRecord:
    word: str
    normalized_word: str
    frequency: float
    source_line: int


def _normalize(word: str) -> str:
    from .morphology import _normalize_word

    return _normalize_word(word)


def read_frequency_list(path: str | Path) -> tuple[FrequencyRecord, ...]:
    """Read a ``word,frequency`` CSV and return stable descending records."""
    path = Path(path)
    try:
        stream = path.open("r", encoding="utf-8", newline="")
    except OSError as exc:
        raise FileNotFoundError(f"frequency list is unavailable: {path}") from exc
    with stream:
        reader = csv.DictReader(stream)
        field_map = {name.strip(): name for name in (reader.fieldnames or [])}
        if "word" not in field_map or "frequency" not in field_map:
            raise ValueError(f"{path}: expected CSV columns word and frequency")
        records: list[FrequencyRecord] = []
        for line_number, row in enumerate(reader, 2):
            word = (row.get(field_map["word"]) or "").strip()
            raw_frequency = (row.get(field_map["frequency"]) or "").strip()
            if not word:
                raise ValueError(f"{path}:{line_number}: word must be non-empty")
            try:
                frequency = float(raw_frequency)
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: invalid frequency {raw_frequency!r}") from exc
            if not math.isfinite(frequency) or frequency < 0:
                raise ValueError(f"{path}:{line_number}: frequency must be finite and nonnegative")
            records.append(FrequencyRecord(word, _normalize(word), frequency, line_number))
    return tuple(sorted(records, key=lambda item: (-item.frequency, item.normalized_word, item.source_line)))


@dataclass(frozen=True)
class OrthographicCandidate:
    word: str
    normalized_word: str
    source: str
    frequency: float | None
    lemma: str | None
    features: tuple[str, ...]
    target_grapheme: str
    group: str
    occurrence_index: int
    left_context: str
    right_context: str
    position: str
    pattern: str
    note: str = "Orthographic candidate selector; not a phone prediction."


def _position(index: int, length: int) -> str:
    if length == 1:
        return "only"
    if index == 0:
        return "initial"
    if index == length - 1:
        return "final"
    return "medial"


def _span_position(start: int, span_length: int, word_length: int) -> str:
    if span_length == word_length:
        return "only"
    if start == 0:
        return "initial"
    if start + span_length == word_length:
        return "final"
    return "medial"


def _letter_patterns(word: str, index: int, target: str) -> tuple[str, ...]:
    left = word[index - 1] if index else ""
    right = word[index + 1] if index + 1 < len(word) else ""
    patterns: list[str] = []
    if left in MONGOLIAN_VOWELS and right in MONGOLIAN_VOWELS:
        patterns.append("VCV")
    elif left in MONGOLIAN_VOWELS:
        patterns.append("VC")
    elif right in MONGOLIAN_VOWELS:
        patterns.append("CV")
    if left and left not in MONGOLIAN_VOWELS and right in MONGOLIAN_VOWELS:
        patterns.append("CV")
    if left in MONGOLIAN_VOWELS and right and right not in MONGOLIAN_VOWELS:
        patterns.append("VC")
    if left in FRONT_VOWELS or right in FRONT_VOWELS:
        patterns.append("front_vowel_neighbor")
    if left in BACK_VOWELS or right in BACK_VOWELS:
        patterns.append("back_vowel_neighbor")
    if target in MONGOLIAN_CONSONANTS and right == "и":
        patterns.append("Ci_candidate")
    if target == "ь":
        patterns.append("soft_sign")
    if target == "ъ":
        patterns.append("hard_sign")
    if right and right not in MONGOLIAN_VOWELS:
        patterns.append("preconsonantal")
    if index == len(word) - 1:
        patterns.append("final")
    return tuple(dict.fromkeys(patterns))


def _targets(group: str) -> tuple[str, ...]:
    normalized = group.upper()
    if normalized == "L":
        return ("л",)
    if normalized == "G":
        return ("г",)
    if normalized == "H":
        return ("х",)
    if normalized in {"PALATALIZATION", "PALATALISATION"}:
        return ("ь", "ъ")
    if normalized == "NG":
        return ("нг",)
    raise ValueError(f"unknown target group: {group}")


def mine_word(
    word: str,
    *,
    source: str,
    frequency: float | None = None,
    lemma: str | None = None,
    features: Sequence[str] = (),
    groups: Sequence[str] = ("L", "G", "H", "PALATALIZATION"),
) -> tuple[OrthographicCandidate, ...]:
    """Mine requested literal contexts from one spelling."""
    normalized = _normalize(word)
    candidates: list[OrthographicCandidate] = []
    normalized_groups = tuple(group.upper() for group in groups)
    for group in normalized_groups:
        if group == "NG":
            continue
        for target in _targets(group):
            positions = [i for i, character in enumerate(normalized) if character == target]
            for occurrence_index in positions:
                left = normalized[max(0, occurrence_index - 1) : occurrence_index]
                right = normalized[occurrence_index + 1 : occurrence_index + 2]
                for pattern in _letter_patterns(normalized, occurrence_index, target):
                    candidates.append(
                        OrthographicCandidate(
                            word=word,
                            normalized_word=normalized,
                            source=source,
                            frequency=frequency,
                            lemma=lemma,
                            features=tuple(features),
                            target_grapheme=target,
                            group=group,
                            occurrence_index=occurrence_index,
                            left_context=left,
                            right_context=right,
                            position=_position(occurrence_index, len(normalized)),
                            pattern=pattern,
                        )
                    )
    # Explicit nг adjacency is a separate orthographic search target.
    if "NG" in normalized_groups:
        for index in range(len(normalized) - 1):
            if normalized[index : index + 2] == "нг":
                candidates.append(
                    OrthographicCandidate(
                        word,
                        normalized,
                        source,
                        frequency,
                        lemma,
                        tuple(features),
                        "нг",
                        "NG",
                        index,
                        normalized[max(0, index - 1) : index],
                        normalized[index + 2 : index + 3],
                        _span_position(index, 2, len(normalized)),
                        "ng",
                    )
                )
    if "PALATALIZATION" in normalized_groups or "PALATALISATION" in normalized_groups:
        for index, character in enumerate(normalized):
            if character in MONGOLIAN_CONSONANTS and index + 1 < len(normalized) and normalized[index + 1] == "и":
                candidates.append(
                    OrthographicCandidate(
                        word,
                        normalized,
                        source,
                        frequency,
                        lemma,
                        tuple(features),
                        character,
                        "PALATALIZATION",
                        index,
                        normalized[max(0, index - 1) : index],
                        normalized[index + 1 : index + 2],
                        _position(index, len(normalized)),
                        "Ci_candidate",
                    )
                )
    return tuple(candidates)


def mine_frequency(
    records: Iterable[FrequencyRecord],
    *,
    groups: Sequence[str],
    min_frequency: float = 0.0,
    limit_per_pattern: int | None = None,
) -> tuple[OrthographicCandidate, ...]:
    candidates: list[OrthographicCandidate] = []
    for record in records:
        if record.frequency < min_frequency:
            continue
        candidates.extend(mine_word(record.word, source="frequency", frequency=record.frequency, groups=groups))
    return _sort_and_limit(candidates, limit_per_pattern)


def mine_unimorph(
    resource: UniMorphKhalkha, *, groups: Sequence[str], limit: int | None = None
) -> tuple[OrthographicCandidate, ...]:
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative or None")
    if limit == 0:
        return ()
    candidates: list[OrthographicCandidate] = []
    seen: set[tuple[str, str, str, int]] = set()
    for analysis in resource.iter_analyses(limit=limit):
        key = ("unimorph_surface", _normalize(analysis.surface), analysis.lemma, analysis.source_line)
        if key in seen:
            continue
        seen.add(key)
        candidates.extend(
            mine_word(
                analysis.surface,
                source="unimorph_surface",
                lemma=analysis.lemma,
                features=analysis.features,
                groups=groups,
            )
        )
    for segmentation in resource.iter_segmentations(limit=limit):
        key = ("unimorph_lemma", _normalize(segmentation.lemma), segmentation.surface, segmentation.source_line)
        if key in seen:
            continue
        seen.add(key)
        candidates.extend(
            mine_word(
                segmentation.lemma,
                source="unimorph_lemma",
                lemma=segmentation.lemma,
                features=segmentation.features,
                groups=groups,
            )
        )
    # ``limit`` bounds source rows, not output contexts. Callers that combine
    # sources apply their output limit after deterministic cross-source sort.
    return _sort_and_limit(candidates, None)


def _sort_and_limit(
    candidates: Iterable[OrthographicCandidate], limit: int | None
) -> tuple[OrthographicCandidate, ...]:
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative or None")
    ordered = sorted(
        candidates,
        key=lambda item: (
            item.group,
            item.pattern,
            -(item.frequency if item.frequency is not None else -1.0),
            item.normalized_word,
            item.source,
            item.occurrence_index,
        ),
    )
    if limit is None:
        return tuple(ordered)
    counts: dict[tuple[str, str], int] = {}
    output: list[OrthographicCandidate] = []
    for item in ordered:
        key = (item.group, item.pattern)
        if counts.get(key, 0) >= limit:
            continue
        counts[key] = counts.get(key, 0) + 1
        output.append(item)
    return tuple(output)


def candidate_to_dict(candidate: OrthographicCandidate) -> dict[str, object]:
    """Serialize without adding any pronunciation field."""
    return asdict(candidate)


# Methods are kept as small adapters so context mining can stream large files.
