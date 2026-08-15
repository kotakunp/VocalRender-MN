#!/usr/bin/env python3
"""Select the native-reference study pool with reviewed metadata only."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from khalkha_frontend import (  # noqa: E402
    ValidationError,
    load_benchmark,
    load_context_annotations,
    load_quotas,
    select_group,
    validate_source_span,
)  # noqa: E402


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def run(config: Path, *, emit_review_queue: bool = False, freeze: bool = False) -> int:
    root = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    manifest_path = _resolve(config.parent, root["manifest"])
    strata_path = _resolve(config.parent, root["selection_strata"])
    annotation_path = _resolve(config.parent, root["context_annotations"])
    manifest = load_benchmark(manifest_path)
    annotations, _ = load_context_annotations(annotation_path, manifest)
    quotas = load_quotas(strata_path)
    alignment_path = _resolve(config.parent, root["alignments"])
    alignment_root = yaml.safe_load(alignment_path.read_text(encoding="utf-8")) or {}
    alignments = {
        entry.get("item_id"): entry for entry in alignment_root.get("alignments", []) if isinstance(entry, dict)
    }
    alignment_statuses = {item_id: entry.get("review_status", "unreviewed") for item_id, entry in alignments.items()}
    known_items = {item.id: item for item in manifest.items}
    for item_id, entry in alignments.items():
        if item_id not in known_items:
            raise ValidationError(f"alignment references unknown item {item_id}")
        if entry.get("review_status") == "approved":
            source_text = entry.get("source_text")
            units = entry.get("lyric_units")
            if source_text != known_items[item_id].text or not isinstance(units, list):
                raise ValidationError(f"approved alignment {item_id} does not match benchmark text")
            validate_source_span(source_text, units)
            if item_id == "MNPHON_161" and [(unit.get("text"), unit.get("source_span")) for unit in units] != [
                ("хүү", [0, 3]),
                ("хэд", [3, 6]),
            ]:
                raise ValidationError("MNPHON_161 must preserve the хүү | хэд regression")
            if not all(entry.get(field) for field in ("reviewer_pseudonym", "review_date", "alignment_note")):
                raise ValidationError(f"approved alignment {item_id} lacks review metadata")
            for unit in units:
                notes = unit.get("notes")
                if (
                    not isinstance(notes, list)
                    or len(notes) != 1
                    or notes[0].get("midi_pitch") != int(root.get("score_midi_pitch", 60))
                    or notes[0].get("note_value") != root.get("score_note", "<NOTE_2>")
                ):
                    raise ValidationError(f"approved alignment {item_id} violates the controlled score")
    unresolved_ids = {item_id for item_id, status in alignment_statuses.items() if status == "alignment_unresolved"}
    groups = {}
    all_ids: list[str] = []
    for group in ("L", "G", "H", "PALATALIZATION"):
        fields = tuple(
            (yaml.safe_load(strata_path.read_text(encoding="utf-8")) or {}).get("diversity_fields", {}).get(group, [])
        )
        result = select_group(
            group,
            manifest,
            annotations,
            quotas,
            size=int(root.get("group_size", 8)),
            fields=fields,
            excluded_ids=unresolved_ids,
        )
        groups[group] = result
        all_ids.extend(result["selected_ids"])
    needs_review = [
        item_id
        for item_id in all_ids
        if item_id not in alignments or alignments[item_id].get("review_status") != "approved"
    ]
    report = {
        "schema_version": 1,
        "study_id": root.get("study_id"),
        "status": "frozen" if freeze else "review_queue",
        "source_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "context_annotations_sha256": hashlib.sha256(annotation_path.read_bytes()).hexdigest(),
        "alignments_sha256": hashlib.sha256(alignment_path.read_bytes()).hexdigest(),
        "groups": groups,
        "selected_items": sorted(all_ids),
        "items_requiring_review": needs_review,
        "selector_version": "native-study-selector-v1",
        "seed_namespace": root.get("seed_namespace"),
        "deterministic_exclusions": sorted(unresolved_ids),
    }
    cycles_path = _resolve(config.parent, root.get("review_cycles", "../results/review_cycles.yaml"))
    cycles_root = yaml.safe_load(cycles_path.read_text(encoding="utf-8")) if cycles_path.exists() else None
    if cycles_root is None:
        cycles_root = {"schema_version": 1, "cycles": []}
    cycles = cycles_root.get("cycles")
    if not isinstance(cycles, list):
        raise ValidationError("review_cycles.cycles must be a list")
    if cycles:
        previous_statuses = cycles[-1].get("alignment_statuses", {})
        for item_id, previous in previous_statuses.items():
            current = alignment_statuses.get(item_id, "unreviewed")
            allowed = (
                previous == current
                or previous == "unreviewed"
                and current
                in {
                    "approved",
                    "alignment_unresolved",
                }
            )
            if not allowed:
                raise ValidationError(
                    f"alignment status transition {item_id}: {previous} -> {current} requires a new study version"
                )
    cycle_material = {
        "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
        "context_annotations_sha256": report["context_annotations_sha256"],
        "alignments_sha256": report["alignments_sha256"],
        "winning_ids": report["selected_items"],
        "deterministic_exclusions": report["deterministic_exclusions"],
    }
    cycle_id = hashlib.sha256(
        json.dumps(cycle_material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    if not cycles or cycles[-1].get("cycle_id") != cycle_id:
        cycles.append(
            {
                "cycle_id": cycle_id,
                **cycle_material,
                "pair_ids": sorted(
                    {
                        annotation.contrast_pair_id
                        for item_id, annotation in annotations.items()
                        if item_id in all_ids and annotation.contrast_pair_id
                    }
                ),
                "diversity_vectors": {name: value["diversity_vector"] for name, value in groups.items()},
                "tie_cohorts": {name: value["tie_cohort"] for name, value in groups.items()},
                "items_requiring_review": needs_review,
                "alignment_statuses": alignment_statuses,
            }
        )
        cycles_path.write_text(yaml.safe_dump(cycles_root, allow_unicode=True, sort_keys=False), encoding="utf-8")
    output_path = _resolve(config.parent, root.get("selection_output", "../results/selection_manifest.yaml"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if freeze:
        if len(all_ids) != 32 or len(set(all_ids)) != 32 or needs_review:
            blocker = output_path.parent / "selection_blocker.json"
            blocker.write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "reason": "freeze requires 32 unique selected items with approved alignment",
                        "selected_count": len(all_ids),
                        "items_requiring_review": needs_review,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(
                f"error: freeze blocked; {len(all_ids)} selected, {len(needs_review)} alignment reviews pending",
                file=sys.stderr,
            )
            return 2
        scores_dir = _resolve(config.parent, root.get("scores_dir", "scores"))
        scores_dir.mkdir(parents=True, exist_ok=True)
        score_checksums = {}
        for item_id in sorted(all_ids):
            alignment = alignments[item_id]
            score = {
                "item_name": item_id,
                "bpm": int(root.get("bpm", 96)),
                "units": [
                    {
                        "text": unit["text"],
                        "source_span": unit["source_span"],
                        "notes": unit["notes"],
                    }
                    for unit in alignment["lyric_units"]
                ],
                "metadata": {
                    "source_text": alignment["source_text"],
                    "alignment_status": alignment["review_status"],
                    "alignment_manifest_sha256": report["alignments_sha256"],
                },
            }
            score_path = scores_dir / f"{item_id}.json"
            serialized = json.dumps(score, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            score_path.write_text(serialized, encoding="utf-8")
            score_checksums[item_id] = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        report["score_checksums"] = score_checksums
        output_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"{len(all_ids)} selected")
        return 0
    output_path.write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if emit_review_queue or not freeze else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--emit-review-queue", action="store_true")
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args(argv)
    try:
        return run(args.config, emit_review_queue=args.emit_review_queue, freeze=args.freeze)
    except (OSError, KeyError, TypeError, ValueError, ValidationError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
