#!/usr/bin/env python3
"""Validate the study kit and operator manifests without claiming recordings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from khalkha_frontend import (  # noqa: E402
    ValidationError,
    load_audio_takes,
    load_benchmark,
    load_ratings,
    validate_related,
)


def validate(study_dir: Path) -> int:
    manifest = load_benchmark(ROOT / "benchmarks/MN-PHON-250/manifest.yaml")
    results = study_dir / "results"
    selection_path = results / "selection_manifest.yaml"
    selected = yaml.safe_load(selection_path.read_text(encoding="utf-8")) or {}
    selected_ids = selected.get("selected_items", [])
    takes_path = study_dir / "results" / "takes.yaml"
    ratings_path = study_dir / "results" / "ratings.yaml"
    takes = load_audio_takes(takes_path) if takes_path.exists() else ()
    ratings = load_ratings(ratings_path) if ratings_path.exists() else ()
    validate_related(manifest, takes, ratings)
    if len(selected_ids) not in {0, 32} or len(set(selected_ids)) != len(selected_ids):
        raise ValidationError("selection must contain zero (blocked draft) or 32 unique IDs")
    if takes or ratings:
        if len(selected_ids) != 32:
            raise ValidationError("takes/ratings cannot be claimed before 32 selected items")
        if selected.get("status") != "frozen":
            raise ValidationError("takes/ratings require a frozen selection")
    report = {
        "selected": len(selected_ids),
        "takes": len(takes),
        "ratings": len(ratings),
        "status": selected.get("status", "unknown"),
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        return validate(args.study_dir)
    except (OSError, KeyError, TypeError, ValueError, ValidationError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
