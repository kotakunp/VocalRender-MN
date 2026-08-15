#!/usr/bin/env python3
"""Validate MN-PHON benchmark, audio-take, and manual-rating manifests."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

try:
    from khalkha_frontend.benchmark import (
        ValidationError,
        load_audio_takes,
        load_benchmark,
        load_ratings,
        validate_related,
    )
except ModuleNotFoundError:  # Allow invocation directly from a source checkout.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from khalkha_frontend.benchmark import (
        ValidationError,
        load_audio_takes,
        load_benchmark,
        load_ratings,
        validate_related,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--audio-manifest", type=Path)
    parser.add_argument("--evaluations", type=Path)
    parser.add_argument("--strict-files", action="store_true")
    parser.add_argument("--json-report", type=Path)
    return parser


def find_repository_root(path: Path) -> Path:
    """Find the checkout root without relying on the process working directory."""

    resolved = path.resolve()
    for candidate in (resolved.parent, *resolved.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return resolved.parent


def display_path(path: Path, repository_root: Path) -> str:
    """Return a non-sensitive repository-relative path, or only a basename."""

    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return path.name


def safe_error(message: str, paths: tuple[Path, ...], repository_root: Path) -> str:
    result = message
    for path in paths:
        result = result.replace(str(path.resolve()), display_path(path, repository_root))
    return result


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest_path = args.manifest
    audio_path = args.audio_manifest or manifest_path.with_name("audio_manifest.yaml")
    evaluations_path = args.evaluations or manifest_path.with_name("evaluations.yaml")
    repository_root = find_repository_root(manifest_path)
    report: dict[str, object] = {
        "manifest": display_path(manifest_path, repository_root),
        "warnings": [],
        "errors": [],
    }
    try:
        manifest = load_benchmark(manifest_path)
        takes = load_audio_takes(audio_path)
        ratings = load_ratings(evaluations_path)
        warnings = validate_related(
            manifest,
            takes,
            ratings,
            strict_files=args.strict_files,
            repository_root=repository_root,
        )
        report.update(
            {
                "item_count": len(manifest.items),
                "valid_items": len(manifest.items),
                "audio_takes": len(takes),
                "ratings": len(ratings),
                "unresolved_expected_phoneme": sum(item.expected_phoneme is None for item in manifest.items),
                "unresolved_expected_phone": sum(item.expected_phone is None for item in manifest.items),
                "groups": dict(Counter(item.target_group for item in manifest.items)),
                "categories": dict(Counter(item.legacy_category for item in manifest.items)),
                "statuses": dict(Counter(item.status.value for item in manifest.items)),
                "sources": dict(Counter(take.source.value for take in takes)),
                "warnings": warnings,
            }
        )
    except (ValidationError, OSError, ValueError) as exc:
        report["errors"] = [safe_error(str(exc), (manifest_path, audio_path, evaluations_path), repository_root)]

    if args.json_report:
        args.json_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["errors"]:
        for error in report["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"{report['valid_items']} valid items; {report['audio_takes']} audio takes; "
        f"{report['ratings']} ratings; {len(report['warnings'])} warnings"
    )
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
