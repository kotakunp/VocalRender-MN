#!/usr/bin/env python3
# flake8: noqa: E501
"""Validate the fail-closed MN-SVS corpus eligibility manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from vocalrender.corpus import CorpusError, json_summary, validate_manifest
except ModuleNotFoundError:  # Allow direct invocation from a source checkout.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from vocalrender.corpus import CorpusError, json_summary, validate_manifest


def find_repository_root(path: Path) -> Path:
    path = path.resolve()
    for candidate in (path.parent, *path.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return path.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args(argv)
    try:
        report = validate_manifest(args.manifest, repository_root=find_repository_root(args.manifest))
    except (CorpusError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    summary = report.summary()
    if args.json_report:
        args.json_report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json_summary(report))
    if report.errors:
        for error in report.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if not report.eligible:
        print("ERROR: zero eligible native Standard Khalkha singing hours remain", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
