#!/usr/bin/env python3
"""Audit reviewed context strata for the native-reference study."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from khalkha_frontend import (  # noqa: E402
    ValidationError,
    load_benchmark,
    load_context_annotations,
    load_quotas,
    quota_count,
)
import yaml  # noqa: E402


def _resolve(base: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (base / candidate).resolve()


def audit(config: Path) -> tuple[dict, int]:
    root = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    manifest_path = _resolve(config.parent, root["manifest"])
    strata_path = _resolve(config.parent, root.get("selection_strata", config.name))
    annotation_path = _resolve(config.parent, root.get("context_annotations", "context_annotations.yaml"))
    manifest = load_benchmark(manifest_path)
    annotations, annotation_root = load_context_annotations(annotation_path, manifest)
    quotas = load_quotas(strata_path)
    report = {
        "manifest_sha256": __import__("hashlib").sha256(manifest_path.read_bytes()).hexdigest(),
        "approved_annotations": sum(a.approved for a in annotations.values()),
        "groups": {},
        "multi_label_items": [],
        "contrast_pairs": [],
    }
    for item_id, annotation in annotations.items():
        labels = sum(
            (
                list(annotation.values(field))
                for field in ("structural_context", "vowel_context_class", "cluster_or_ng_context", "trigger_type")
            ),
            [],
        )
        if len(labels) > len(set(labels)):
            report["multi_label_items"].append(item_id)
    for group in ("L", "G", "H", "PALATALIZATION"):
        group_ids = [item.id for item in manifest.items if item.target_group == group]
        rows = []
        ok = True
        for quota in (q for q in quotas if q.group == group):
            count = quota_count(group_ids, annotations, quota)
            feasible = count >= quota.minimum_count
            rows.append(
                {
                    "id": quota.id,
                    "count": count,
                    "minimum": quota.minimum_count,
                    "required": quota.required,
                    "feasible": feasible,
                }
            )
            if quota.required and not feasible:
                ok = False
        report["groups"][group] = {
            "candidate_count": sum(item_id in annotations and annotations[item_id].approved for item_id in group_ids),
            "quotas": rows,
            "required_quotas_feasible": ok,
        }
    status = 0 if all(row["required_quotas_feasible"] for row in report["groups"].values()) else 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        _, status = audit(args.config)
        return status
    except (OSError, KeyError, ValidationError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
