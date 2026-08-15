#!/usr/bin/env python3
"""Run a read-only Mongolian tokenizer audit without loading model weights."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from khalkha_frontend.morphology import UniMorphKhalkha  # noqa: E402
from khalkha_frontend.tokenizer_audit import (  # noqa: E402
    aggregate_records,
    aggregate_by_benchmark_group,
    aggregate_by_character,
    aggregate_by_word_length,
    collect_benchmark,
    collect_frequency,
    collect_special_probes,
    collect_unimorph,
    deduplicate_samples,
    hash_files,
    record_to_dict,
    sha256_file,
    tokenize_sample,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--resources-root", type=Path, default=Path("resources"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--offline", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--frequency-limit", type=int, default=None)
    parser.add_argument("--unimorph-limit", type=int, default=None)
    parser.add_argument("--fragmentation-threshold", type=float, default=None)
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--fail-on-unknown", action="store_true")
    parser.add_argument("--fail-on-roundtrip-mismatch", action="store_true")
    return parser.parse_args(argv)


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _load_tokenizer(checkpoint: Path, offline: bool):
    try:
        from transformers import LlamaTokenizerFast
    except ImportError as exc:
        raise RuntimeError("transformers is required for the real tokenizer audit") from exc
    kwargs = {"local_files_only": True} if offline else {}
    # Deliberately load only tokenizer files. No AutoModel/model checkpoint call
    # belongs in this audit.
    return LlamaTokenizerFast.from_pretrained(str(checkpoint), **kwargs)


def _config(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _benchmark_revision(path: Path) -> str | None:
    try:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (ImportError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    metadata = payload.get("benchmark", {})
    if isinstance(metadata, dict):
        return str(metadata.get("version")) if metadata.get("version") is not None else None
    return None


def _markdown(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    records = payload["records"]
    special = [item for item in records if item["source"] == "special_probe"]
    fragmented = sorted(records, key=lambda item: item["tokens_per_character"], reverse=True)[:20]
    lines = [
        "# VocalRender-Pro Mongolian tokenizer audit",
        "",
        "## Baseline",
        "",
        f"- Checkpoint: `{payload['checkpoint']}`",
        f"- Tokenizer class: `{payload['tokenizer']['class']}`",
        f"- Audited records: {aggregate['count']}",
        f"- Unknown rate: {aggregate['unknown_rate']:.4f}",
        f"- Round-trip mismatch rate: {aggregate['roundtrip_mismatch_rate']:.4f}",
        "",
        "## Required character probes",
        "",
        "| Character | Code points | Tokens | Unknown |",
        "|---|---|---:|---:|",
    ]
    for item in special:
        lines.append(
            f"| `{item['original_text']}` | `{', '.join(item['code_points'])}` | "
            f"{item['token_count']} | {item['unknown_token_count']} |"
        )
    lines += [
        "",
        "## Fragmentation summary",
        "",
        f"- Median tokens/character: {aggregate['median_tokens_per_character']}",
        f"- P90: {aggregate['p90_tokens_per_character']}",
        f"- P95: {aggregate['p95_tokens_per_character']}",
        f"- Max: {aggregate['max_tokens_per_character']}",
        f"- Fragmented records: {aggregate['fragmented_count']}",
        "",
        "| Source item | Text | Tokens/character | Unknown |",
        "|---|---|---:|---:|",
    ]
    for item in fragmented:
        lines.append(
            f"| `{item['source_item_id']}` | `{item['normalized_text']}` | "
            f"{item['tokens_per_character']:.3f} | {item['unknown_token_count']} |"
        )
    lines += ["", "## Benchmark target groups", "", "| Group | Records | Unknown rate |", "|---|---:|---:|"]
    for group, summary in payload.get("aggregate_by_benchmark_group", {}).items():
        lines.append(f"| `{group}` | {summary['count']} | {summary['unknown_rate']:.4f} |")
    lines += ["", "## Word-length buckets", "", "| Bucket | Records | Median tokens/character |", "|---|---:|---:|"]
    for bucket, summary in payload.get("aggregate_by_word_length", {}).items():
        lines.append(f"| `{bucket}` | {summary['count']} | {summary['median_tokens_per_character']} |")
    lines += [
        "",
        "## Limitations",
        "",
        "Token fragmentation and unknown-token behavior describe tokenizer mechanics only; "
        "they are not pronunciation or native-quality evidence.",
        "Do not modify or extend the tokenizer until these results are reviewed with audio and benchmark evidence.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = _config(args.config)
    offline = args.offline if args.offline is not None else bool(config.get("offline", True))
    frequency_limit = (
        args.frequency_limit if args.frequency_limit is not None else int(config.get("frequency_limit", 1000))
    )
    unimorph_limit = args.unimorph_limit if args.unimorph_limit is not None else int(config.get("unimorph_limit", 1000))
    fragmentation_threshold = (
        args.fragmentation_threshold
        if args.fragmentation_threshold is not None
        else float(config.get("fragmentation_threshold", 1.5))
    )
    generated_at = args.generated_at or config.get("generated_at") or datetime.now(timezone.utc).isoformat()
    if frequency_limit < 0 or unimorph_limit < 0:
        raise SystemExit("sample limits must be non-negative")
    checkpoint = args.checkpoint.resolve()
    before_hashes = hash_files(checkpoint)
    before_files = tuple(
        sorted(path.relative_to(checkpoint).as_posix() for path in checkpoint.rglob("*") if path.is_file())
    )
    tokenizer = _load_tokenizer(checkpoint, offline)
    try:
        tokenizer_length = len(tokenizer)
    except TypeError:
        tokenizer_length = None
    resources = args.resources_root.resolve()
    samples = list(collect_special_probes()) + list(collect_benchmark(args.benchmark))
    frequency_path = resources / "lexicon" / "most_frequent_words.csv"
    warnings: list[str] = []
    if frequency_path.is_file():
        samples.extend(collect_frequency(frequency_path, frequency_limit))
    else:
        warnings.append(f"frequency input missing: {_relative(frequency_path)}")
    unimorph_path = resources / "unimorph_khk"
    if (unimorph_path / "khk").is_file():
        samples.extend(collect_unimorph(UniMorphKhalkha(unimorph_path), unimorph_limit))
    else:
        warnings.append(f"UniMorph input missing: {_relative(unimorph_path)}")
    samples = list(deduplicate_samples(samples))
    records = [
        tokenize_sample(tokenizer, sample, fragmentation_threshold=fragmentation_threshold) for sample in samples
    ]
    after_hashes = hash_files(checkpoint)
    after_files = tuple(
        sorted(path.relative_to(checkpoint).as_posix() for path in checkpoint.rglob("*") if path.is_file())
    )
    if before_hashes != after_hashes or before_files != after_files:
        raise RuntimeError("checkpoint tokenizer file hashes or file list changed during read-only audit")
    by_source: dict[str, Any] = {}
    for source in sorted({record.source for record in records}):
        by_source[source] = aggregate_records([record for record in records if record.source == source])
    source_ids = sorted({sample.source for sample in samples})
    input_sources = [
        {
            "id": "benchmark",
            "path": _relative(args.benchmark),
            "revision": {
                "sha256": sha256_file(args.benchmark),
                "manifest_version": _benchmark_revision(args.benchmark),
            },
        },
        {"id": "checkpoint", "path": _relative(checkpoint), "revision": dict(before_hashes)},
    ]
    if frequency_path.is_file():
        input_sources.append(
            {"id": "frequency", "path": _relative(frequency_path), "revision": {"sha256": sha256_file(frequency_path)}}
        )
    if (unimorph_path / "khk").is_file():
        for filename in ("khk", "khk.segmentations", "khk.derivations"):
            resource_file = unimorph_path / filename
            if resource_file.is_file():
                input_sources.append(
                    {
                        "id": f"unimorph_khk:{filename}",
                        "path": _relative(resource_file),
                        "revision": {"sha256": sha256_file(resource_file)},
                    }
                )
    payload: dict[str, Any] = {
        "schema_version": "tokenizer-audit/v1",
        "tool_version": "1.0",
        "generated_at": generated_at,
        "checkpoint": _relative(checkpoint),
        "tokenizer": {
            "class": type(tokenizer).__name__,
            "hashes": dict(before_hashes),
            "length": tokenizer_length,
            "vocab_size": getattr(tokenizer, "vocab_size", None),
            "special_tokens": list(getattr(tokenizer, "all_special_tokens", ()) or ()),
            "unk_token": getattr(tokenizer, "unk_token", None),
            "unk_token_id": getattr(tokenizer, "unk_token_id", None),
        },
        "config_path": _relative(args.config) if args.config else None,
        "config": {
            "fragmentation_threshold": fragmentation_threshold,
            "frequency_limit": frequency_limit,
            "unimorph_limit": unimorph_limit,
            "offline": offline,
        },
        "input_source_ids": source_ids,
        "input_sources": input_sources,
        "aggregate": aggregate_records(records),
        "aggregate_by_source": by_source,
        "aggregate_by_benchmark_group": aggregate_by_benchmark_group(records),
        "aggregate_by_character": aggregate_by_character(records),
        "aggregate_by_word_length": aggregate_by_word_length(records),
        "records": [record_to_dict(record) for record in records],
        "warnings": warnings,
        "limitations": ["Tokenization is not pronunciation/native-quality evidence."],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "tokenizer_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.output_dir / "tokenizer_audit.md").write_text(_markdown(payload), encoding="utf-8")
    if args.fail_on_unknown and any(record.has_unknown for record in records):
        return 2
    if args.fail_on_roundtrip_mismatch and any(record.roundtrip_mismatch for record in records):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
