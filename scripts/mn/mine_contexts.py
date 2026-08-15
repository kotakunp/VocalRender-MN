#!/usr/bin/env python3
"""Mine orthographic benchmark candidates from text resources only."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from khalkha_frontend.context_mining import (  # noqa: E402
    candidate_to_dict,
    mine_frequency,
    mine_unimorph,
    read_frequency_list,
)
from khalkha_frontend.morphology import UniMorphKhalkha  # noqa: E402


def _display_path(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _config(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    try:
        import yaml

        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except ImportError:
        # The checked-in config is intentionally simple; avoid making YAML a
        # requirement for the library or help command.
        return {}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resources-root", type=Path, default=Path("resources"))
    parser.add_argument("--group", "--pattern", dest="groups", action="append", default=[])
    parser.add_argument("--source", choices=("frequency", "unimorph", "both"))
    parser.add_argument("--limit-per-pattern", type=int, default=None)
    parser.add_argument("--min-frequency", type=float, default=None)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--unimorph-limit", type=int, default=None)
    parser.add_argument("--generated-at", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.limit_per_pattern is not None and args.limit_per_pattern < 0:
        raise SystemExit("--limit-per-pattern must be non-negative")
    config = _config(args.config)
    configured_groups = config.get("groups", ())
    groups = tuple(args.groups) or tuple(configured_groups) or ("L", "G", "H", "PALATALIZATION", "NG")
    source = args.source or str(config.get("source", "both"))
    limit_per_pattern = (
        args.limit_per_pattern if args.limit_per_pattern is not None else config.get("limit_per_pattern")
    )
    min_frequency = args.min_frequency if args.min_frequency is not None else float(config.get("min_frequency", 0.0))
    unimorph_limit = args.unimorph_limit if args.unimorph_limit is not None else int(config.get("unimorph_limit", 5000))
    generated_at = args.generated_at or config.get("generated_at") or datetime.now(timezone.utc).isoformat()
    if limit_per_pattern is not None and int(limit_per_pattern) < 0:
        raise SystemExit("--limit-per-pattern must be non-negative")
    if unimorph_limit < 0:
        raise SystemExit("--unimorph-limit must be non-negative")
    if source not in {"frequency", "unimorph", "both"}:
        raise SystemExit("source must be frequency, unimorph, or both")
    resources_root = args.resources_root
    if not resources_root.is_absolute():
        resources_root = (Path.cwd() / resources_root).resolve()
    candidates = []
    warnings: list[str] = []
    source_ids: list[str] = []
    if source in {"frequency", "both"}:
        frequency_path = resources_root / "lexicon" / "most_frequent_words.csv"
        if frequency_path.is_file():
            records = read_frequency_list(frequency_path)
            candidates.extend(
                mine_frequency(records, groups=groups, min_frequency=min_frequency, limit_per_pattern=limit_per_pattern)
            )
            source_ids.append("lexicon/most_frequent_words.csv")
        else:
            warnings.append(f"missing optional frequency list: {_display_path(frequency_path)}")
    if source in {"unimorph", "both"}:
        unimorph_path = resources_root / "unimorph_khk"
        if (unimorph_path / "khk").is_file():
            resource = UniMorphKhalkha(unimorph_path)
            candidates.extend(mine_unimorph(resource, groups=groups, limit=unimorph_limit))
            source_ids.append("unimorph_khk")
        else:
            warnings.append(f"missing optional UniMorph directory: {_display_path(unimorph_path)}")
    # Stable deduplication across source readers, retaining distinct provenance.
    unique = {}
    for candidate in candidates:
        key = (
            candidate.source,
            candidate.normalized_word,
            candidate.occurrence_index,
            candidate.group,
            candidate.pattern,
            candidate.lemma,
            candidate.features,
        )
        unique[key] = candidate
    ordered = sorted(
        unique.values(),
        key=lambda item: (
            item.group,
            item.pattern,
            -(item.frequency if item.frequency is not None else -1.0),
            item.normalized_word,
            item.source,
            item.occurrence_index,
        ),
    )
    if limit_per_pattern is not None:
        counts: dict[tuple[str, str], int] = {}
        limited = []
        for item in ordered:
            key = (item.group, item.pattern)
            if counts.get(key, 0) >= int(limit_per_pattern):
                continue
            counts[key] = counts.get(key, 0) + 1
            limited.append(item)
        ordered = limited
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "context-mining/v1",
        "command": "scripts/mn/mine_contexts.py",
        "config": _display_path(args.config) if args.config else None,
        "source_manifest_ids": source_ids,
        "generated_at": generated_at,
        "groups": groups,
        "parameters": {
            "source": source,
            "limit_per_pattern": limit_per_pattern,
            "min_frequency": min_frequency,
            "unimorph_limit": unimorph_limit,
        },
        "candidates": [candidate_to_dict(item) for item in ordered],
        "warnings": warnings,
    }
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.output_csv:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        fields = list(candidate_to_dict(ordered[0]).keys()) if ordered else ["word", "normalized_word"]
        with args.output_csv.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for item in ordered:
                writer.writerow(candidate_to_dict(item))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
