#!/usr/bin/env python3
"""Fail-closed CUDA, VRAM, and workspace preflight."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from vocalrender.runtime_preflight import (  # noqa: E402
    PreflightPolicy,
    run_preflight,
    write_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-cuda", action="store_true", help="fail unless CUDA is available")
    parser.add_argument("--allow-cpu", action="store_true", help="explicitly permit CPU execution")
    parser.add_argument("--task", default="inference", help="task label persisted in operator logs")
    parser.add_argument("--dtype", default="float16", help="requested dtype: float16, bfloat16, or float32")
    parser.add_argument("--workspace", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument("--min-free-vram-gib", type=float, default=None)
    parser.add_argument("--min-free-storage-gib", type=float, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_preflight(
        policy=PreflightPolicy(
            require_cuda=args.require_cuda,
            allow_cpu=args.allow_cpu,
            requested_dtype=args.dtype,
            min_free_vram_gib=args.min_free_vram_gib,
            min_free_storage_gib=args.min_free_storage_gib,
        ),
        workspace=args.workspace,
        checkpoint_dir=args.checkpoint_dir,
    )
    report = {"task": args.task, **result.to_dict()}
    if args.json_out is not None:
        write_report(result, args.json_out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
