#!/usr/bin/env python3
# flake8: noqa: E501
"""Generate and verify a deterministic leakage-safe MN-SVS split manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from vocalrender.corpus import (
        CorpusError,
        generate_splits,
        manifest_sha256,
        validate_manifest,
        verify_splits,
        write_yaml,
    )
except ModuleNotFoundError:  # Allow direct invocation from a source checkout.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from vocalrender.corpus import (
        CorpusError,
        generate_splits,
        manifest_sha256,
        validate_manifest,
        verify_splits,
        write_yaml,
    )


def find_repository_root(path: Path) -> Path:
    path = path.resolve()
    for candidate in (path.parent, *path.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return path.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", default="mn-svs-v1")
    parser.add_argument("--new-version", action="store_true", help="explicitly permit replacing a frozen output")
    args = parser.parse_args(argv)
    if args.output.exists() and not args.new_version:
        print("ERROR: split output already exists; choose a new output or pass --new-version", file=sys.stderr)
        return 1
    try:
        report = validate_manifest(args.manifest, repository_root=find_repository_root(args.manifest))
        split_manifest = generate_splits(report, manifest_sha256=manifest_sha256(args.manifest), seed=args.seed)
        verify_splits(report, split_manifest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_yaml(args.output, split_manifest)
    except (CorpusError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "generated deterministic split: "
        + ", ".join(f"{name}={len(ids)}" for name, ids in split_manifest["splits"].items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
