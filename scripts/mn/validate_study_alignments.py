#!/usr/bin/env python3
"""Validate manually supplied raw-Cyrillic lyric-to-note alignments."""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from khalkha_frontend import ValidationError, load_benchmark, validate_source_span  # noqa: E402


def validate(path: Path) -> int:
    root = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = root.get("alignments", [])
    if not isinstance(entries, list):
        raise ValidationError("alignments must be a list")
    manifest = load_benchmark(ROOT / "benchmarks/MN-PHON-250/manifest.yaml")
    known = {item.id: item for item in manifest.items}
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValidationError(f"alignments[{index}] must be a mapping")
        item_id = entry.get("item_id")
        if item_id in seen:
            raise ValidationError(f"duplicate alignment {item_id}")
        if item_id not in known:
            raise ValidationError(f"unknown alignment item {item_id}")
        seen.add(item_id)
        source_text = entry.get("source_text")
        if (
            not isinstance(source_text, str)
            or source_text != unicodedata.normalize("NFC", source_text)
            or any(ch.isspace() for ch in source_text)
        ):
            raise ValidationError(f"{item_id}: source_text must be NFC and whitespace-free")
        if source_text != known[item_id].text:
            raise ValidationError(f"{item_id}: source_text does not match benchmark text")
        if entry.get("whitespace_policy") != "reject_whitespace":
            raise ValidationError(f"{item_id}: whitespace_policy must be reject_whitespace")
        if entry.get("alignment_complexity") not in {"single_unit", "multi_unit"}:
            raise ValidationError(f"{item_id}: invalid alignment_complexity")
        units = entry.get("lyric_units")
        if not isinstance(units, list):
            raise ValidationError(f"{item_id}: lyric_units must be a list")
        validate_source_span(source_text, units)
        if item_id == "MNPHON_161":
            expected = [("хүү", [0, 3]), ("хэд", [3, 6])]
            actual = [(unit.get("text"), unit.get("source_span")) for unit in units]
            if actual != expected or entry.get("alignment_complexity") != "multi_unit":
                raise ValidationError("MNPHON_161 must preserve the хүү | хэд two-unit regression")
        for unit_index, unit in enumerate(units):
            notes = unit.get("notes")
            if not isinstance(notes, list) or len(notes) != 1:
                raise ValidationError(f"{item_id} unit {unit_index}: exactly one note required")
            note = notes[0]
            if note.get("midi_pitch") != 60 or note.get("note_value") != "<NOTE_2>":
                raise ValidationError(f"{item_id} unit {unit_index}: controlled study requires MIDI 60/<NOTE_2>")
        status = entry.get("review_status")
        if status not in {"unreviewed", "approved", "alignment_unresolved"}:
            raise ValidationError(f"{item_id}: invalid review_status")
        if status == "approved" and not all(
            entry.get(field) for field in ("reviewer_pseudonym", "review_date", "alignment_note")
        ):
            raise ValidationError(f"{item_id}: approved alignment requires reviewer pseudonym, date, and note")
        if status == "alignment_unresolved" and not entry.get("alignment_note"):
            raise ValidationError(f"{item_id}: unresolved alignment requires reason")
    print(
        f"{len(entries)} alignment records valid; approved={sum(e.get('review_status') == 'approved' for e in entries)}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        return validate(args.path)
    except (OSError, KeyError, TypeError, ValueError, ValidationError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
