#!/usr/bin/env python3
"""Validate an explicit Khalkha score and serialize VocalRender JSON.

This command performs normalization and alignment validation only.  It never
loads a checkpoint, invokes inference, guesses syllable boundaries, or maps
orthography to phones.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from khalkha_frontend import normalize_text  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="neutral JSON score with explicit lyric units and note arrays")
    parser.add_argument("--output", type=Path, default=Path("-"), help="output JSON path, or - for stdout")
    parser.add_argument("--force", action="store_true", help="allow replacing an existing output file")
    return parser.parse_args(argv)


def _issue_dict(issue: Any) -> dict[str, Any]:
    return {
        "kind": issue.kind.value,
        "original": issue.original,
        "start": issue.start,
        "end": issue.end,
        "message": issue.message,
    }


def _normalize_unit_text(text: str):
    # AP/SP are explicit upstream silence markers. Preserve their spelling and
    # case; ordinary Mongolian lyric units use conservative normalization.
    if text in {"AP", "SP"}:
        return normalize_text(text, lowercase=False)
    return normalize_text(text)


def _parse_pronunciation(raw: Any, normalized_text: str, path: str):
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must be an object when supplied")
    allowed = {
        "orthographic_text",
        "phonemic_symbols",
        "surface_phones",
        "status",
        "evidence_refs",
        "manual_override",
    }
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"{path} contains unsupported fields: {sorted(unknown)!r}")
    from khalkha_frontend import PronunciationUnit, ResolutionStatus

    try:
        status = ResolutionStatus(raw.get("status", ResolutionStatus.RESEARCH_REQUIRED.value))
        return PronunciationUnit(
            orthographic_text=raw.get("orthographic_text", normalized_text),
            phonemic_symbols=raw.get("phonemic_symbols"),
            surface_phones=raw.get("surface_phones"),
            status=status,
            evidence_refs=tuple(raw.get("evidence_refs", ())),
            manual_override=raw.get("manual_override"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path}: {exc}") from exc


def _load_score(path: Path) -> Any:
    # Keep ``--help`` usable in a foundation-only checkout; the adapter is the
    # only optional coupling and is imported when an actual conversion starts.
    from khalkha_frontend.vocalrender_adapter import KhalkhaScore, LyricScoreUnit, ScoreNote

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("input JSON must be an object containing explicit units")
    units_raw = raw.get("units")
    if not isinstance(units_raw, list) or not units_raw:
        raise ValueError(
            "input must provide non-empty 'units' with explicit lyric-to-note alignment; "
            "the adapter will not guess a split from full text"
        )
    units: list[LyricScoreUnit] = []
    diagnostics: list[dict[str, Any]] = []
    for index, unit_raw in enumerate(units_raw):
        if not isinstance(unit_raw, dict):
            raise ValueError(f"units[{index}] must be an object")
        text = unit_raw.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"units[{index}].text must be non-empty")
        normalized = _normalize_unit_text(text)
        diagnostics.extend({"unit_index": index, **_issue_dict(issue)} for issue in normalized.issues)
        notes_raw = unit_raw.get("notes")
        if not isinstance(notes_raw, list) or not notes_raw:
            raise ValueError(f"units[{index}].notes must be a non-empty list; alignment is explicit")
        notes = []
        for note_index, note_raw in enumerate(notes_raw):
            if not isinstance(note_raw, dict):
                raise ValueError(f"units[{index}].notes[{note_index}] must be an object")
            try:
                notes.append(
                    ScoreNote(
                        midi_pitch=note_raw["midi_pitch"],
                        note_value=note_raw["note_value"],
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"units[{index}].notes[{note_index}]: {exc}") from exc
        units.append(
            LyricScoreUnit(
                text=normalized.normalized,
                notes=tuple(notes),
                pronunciation=_parse_pronunciation(
                    unit_raw.get("pronunciation"),
                    normalized.normalized,
                    f"units[{index}].pronunciation",
                ),
                source_span=unit_raw.get("source_span"),
            )
        )
    metadata_raw = raw.get("metadata", {})
    if not isinstance(metadata_raw, dict):
        raise ValueError("metadata must be an object when supplied")
    metadata = dict(metadata_raw)
    metadata["normalization_diagnostics"] = diagnostics
    return KhalkhaScore(
        units=tuple(units),
        bpm=raw.get("bpm"),
        item_name=raw.get("item_name"),
        prompt_audio=raw.get("prompt_audio"),
        metadata=metadata,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.output != Path("-") and args.output.exists() and not args.force:
        print(
            f"error: refusing to overwrite existing output: {args.output}; pass --force to replace it", file=sys.stderr
        )
        return 2
    try:
        score = _load_score(args.input)
        from khalkha_frontend.vocalrender_adapter import to_vocalrender_entry, validate_vocalrender_entry

        entry = to_vocalrender_entry(score)
        validate_vocalrender_entry(entry)
    except (OSError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps([entry], ensure_ascii=False, indent=2) + "\n"
    if args.output == Path("-"):
        sys.stdout.buffer.write(rendered.encode("utf-8"))
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
