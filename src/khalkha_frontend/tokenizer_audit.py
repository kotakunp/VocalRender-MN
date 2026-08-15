"""Read-only, tokenizer-agnostic Mongolian tokenization audit utilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Protocol, Sequence
import unicodedata


class TokenizerLike(Protocol):
    unk_token: str | None
    unk_token_id: int | None

    def __call__(self, text: str, **kwargs: Any) -> Mapping[str, Any]: ...
    def decode(self, token_ids: Sequence[int], **kwargs: Any) -> str: ...
    def convert_ids_to_tokens(self, token_ids: Sequence[int]) -> Sequence[str]: ...


@dataclass(frozen=True)
class AuditSample:
    source: str
    source_item_id: str
    text: str
    normalized_text: str
    target_group: str | None = None


@dataclass(frozen=True)
class TokenizationRecord:
    source: str
    source_item_id: str
    original_text: str
    normalized_text: str
    code_points: tuple[str, ...]
    token_ids: tuple[int, ...]
    token_strings: tuple[str, ...]
    character_count: int
    token_count: int
    tokens_per_character: float
    unknown_token_count: int
    has_unknown: bool
    decoded_text: str
    roundtrip_mismatch: bool
    fragmented: bool
    syllable_count: int | None = None
    tokens_per_syllable: float | None = None
    target_group: str | None = None


@dataclass(frozen=True)
class TokenizerSnapshot:
    files: tuple[tuple[str, str], ...]
    tokenizer_class: str
    tokenizer_length: int | None
    special_tokens: tuple[str, ...]
    unk_token: str | None
    unk_token_id: int | None


def normalize_audit_text(text: str) -> str:
    return unicodedata.normalize("NFC", " ".join(text.split()))


def percentile(values: Sequence[float], quantile: float) -> float | None:
    """Linear percentile; empty inputs produce JSON-friendly ``None``."""
    if not values:
        return None
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be in [0, 1]")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = quantile * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return float(ordered[low])
    return float(ordered[low] + (ordered[high] - ordered[low]) * (position - low))


def _token_values(encoded: Mapping[str, Any], tokenizer: TokenizerLike) -> tuple[int, ...]:
    values = encoded.get("input_ids", ())
    if hasattr(values, "tolist"):
        values = values.tolist()
    if values and isinstance(values[0], (list, tuple)):
        values = values[0]
    return tuple(int(item) for item in values)


def tokenize_sample(
    tokenizer: TokenizerLike,
    sample: AuditSample,
    *,
    fragmentation_threshold: float = 1.5,
    max_tokens_in_record: int = 128,
    syllable_count: int | None = None,
) -> TokenizationRecord:
    normalized = normalize_audit_text(sample.text)
    encoded = tokenizer(normalized, add_special_tokens=False)
    token_ids = _token_values(encoded, tokenizer)
    bounded_ids = token_ids[:max_tokens_in_record]
    strings = tuple(str(item) for item in tokenizer.convert_ids_to_tokens(bounded_ids))
    unk_id = getattr(tokenizer, "unk_token_id", None)
    unk_token = getattr(tokenizer, "unk_token", None)
    if unk_id is not None:
        unknown_count = sum(item == unk_id for item in token_ids)
    else:
        all_strings = tokenizer.convert_ids_to_tokens(token_ids)
        unknown_count = sum(str(item) == unk_token for item in all_strings)
    decoded = str(tokenizer.decode(token_ids, skip_special_tokens=False))
    char_count = len(normalized)
    ratio = len(token_ids) / char_count if char_count else 0.0
    return TokenizationRecord(
        source=sample.source,
        source_item_id=sample.source_item_id,
        original_text=sample.text,
        normalized_text=normalized,
        code_points=tuple(f"U+{ord(char):04X}" for char in normalized),
        token_ids=tuple(bounded_ids),
        token_strings=strings,
        character_count=char_count,
        token_count=len(token_ids),
        tokens_per_character=ratio,
        unknown_token_count=unknown_count,
        has_unknown=unknown_count > 0,
        decoded_text=decoded,
        roundtrip_mismatch=decoded != normalized,
        fragmented=ratio > fragmentation_threshold,
        target_group=sample.target_group,
        syllable_count=syllable_count,
        tokens_per_syllable=(len(token_ids) / syllable_count if syllable_count else None),
    )


def aggregate_records(records: Sequence[TokenizationRecord]) -> dict[str, Any]:
    ratios = [record.tokens_per_character for record in records]
    result: dict[str, Any] = {
        "count": len(records),
        "median_tokens_per_character": float(median(ratios)) if ratios else None,
        "p90_tokens_per_character": percentile(ratios, 0.90),
        "p95_tokens_per_character": percentile(ratios, 0.95),
        "max_tokens_per_character": max(ratios) if ratios else None,
        "unknown_rate": (sum(record.has_unknown for record in records) / len(records) if records else 0.0),
        "roundtrip_mismatch_rate": (
            sum(record.roundtrip_mismatch for record in records) / len(records) if records else 0.0
        ),
        "fragmented_count": sum(record.fragmented for record in records),
        "histogram": _histogram(ratios),
    }
    return result


def word_length_bucket(length: int) -> str:
    if length <= 0:
        return "0"
    if length <= 3:
        return "1-3"
    if length <= 7:
        return "4-7"
    if length <= 11:
        return "8-11"
    return "12+"


def aggregate_by_benchmark_group(records: Sequence[TokenizationRecord]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[TokenizationRecord]] = {}
    for record in records:
        if record.source == "benchmark":
            groups.setdefault(record.target_group or "UNKNOWN", []).append(record)
    return {group: aggregate_records(groups[group]) for group in sorted(groups)}


def aggregate_by_word_length(records: Sequence[TokenizationRecord]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[TokenizationRecord]] = {}
    for record in records:
        bucket = word_length_bucket(record.character_count)
        buckets.setdefault(bucket, []).append(record)
    return {bucket: aggregate_records(buckets[bucket]) for bucket in sorted(buckets)}


def aggregate_by_character(records: Sequence[TokenizationRecord]) -> dict[str, dict[str, Any]]:
    """Aggregate the required one-character special probes individually."""
    characters: dict[str, list[TokenizationRecord]] = {}
    for record in records:
        if record.source == "special_probe":
            characters.setdefault(record.normalized_text, []).append(record)
    return {character: aggregate_records(characters[character]) for character in sorted(characters)}


def _histogram(values: Sequence[float]) -> dict[str, int]:
    buckets = {"0-1": 0, "1-2": 0, "2-3": 0, "3+": 0}
    for value in values:
        key = "0-1" if value <= 1 else "1-2" if value <= 2 else "2-3" if value <= 3 else "3+"
        buckets[key] += 1
    return buckets


def collect_special_probes() -> tuple[AuditSample, ...]:
    characters = "ӨөҮүЁёЬьЪъ"
    return tuple(
        AuditSample("special_probe", f"char-{index:02d}", character, character)
        for index, character in enumerate(characters, 1)
    )


def collect_benchmark(path: str | Path) -> tuple[AuditSample, ...]:
    """Collect canonical ``items`` or legacy ``sections`` benchmark values."""
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to read benchmark manifests") from exc
    # BaseLoader keeps legacy zero-padded item keys such as ``008`` as text;
    # SafeLoader would interpret some of them as YAML 1.1 octal integers.
    payload = yaml.load(Path(path).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    found: list[AuditSample] = []

    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        for item in payload["items"]:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id") or item.get("item_id")
            text = item.get("text")
            if item_id is None or not isinstance(text, str):
                continue
            found.append(
                AuditSample(
                    "benchmark",
                    f"benchmark:{item_id}",
                    text,
                    normalize_audit_text(text),
                    str(item["target_group"]) if item.get("target_group") else None,
                )
            )
        return tuple(found)

    sections = payload.get("sections", {}) if isinstance(payload, dict) else {}

    def walk(value: Any, section: str, target_group: str | None) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                walk(nested, f"{section}/{key}" if section else str(key), target_group)
        elif isinstance(value, str):
            numeric = section.split("/")[-1]
            if numeric.isdigit():
                source_id = f"benchmark:{int(numeric):03d}"
            else:
                source_id = f"benchmark:{section}"
            found.append(AuditSample("benchmark", source_id, value, normalize_audit_text(value), target_group))

    for name, section in (sections.items() if isinstance(sections, dict) else ()):
        walk(section, str(name), str(name))
    return tuple(
        sorted(
            found,
            key=lambda item: (
                (
                    int(item.source_item_id.rsplit(":", 1)[-1])
                    if item.source_item_id.rsplit(":", 1)[-1].isdigit()
                    else 10**9
                ),
                item.source_item_id,
            ),
        )
    )


def collect_frequency(path: str | Path, limit: int) -> tuple[AuditSample, ...]:
    if limit < 0:
        raise ValueError("limit must be non-negative")
    from .context_mining import read_frequency_list

    rows = read_frequency_list(path)
    return tuple(
        AuditSample("frequency", f"frequency:{index:06d}", row.word, row.normalized_word)
        for index, row in enumerate(rows[:limit], 1)
    )


def collect_unimorph(resource: Any, limit: int) -> tuple[AuditSample, ...]:
    if limit < 0:
        raise ValueError("limit must be non-negative")
    if limit == 0:
        return ()
    surfaces = list(resource.iter_analyses())
    segmentations = list(resource.iter_segmentations()) if hasattr(resource, "iter_segmentations") else []

    def sample_even(rows: list[Any], cap: int) -> list[Any]:
        if cap <= 0 or not rows:
            return []
        if len(rows) <= cap:
            return rows
        if cap == 1:
            indices = [0]
        elif cap == 2:
            indices = [0, len(rows) - 1]
        else:
            indices = [int(position * (len(rows) - 1) / (cap - 1) + 0.5) for position in range(cap)]
        return [rows[index] for index in indices]

    if not segmentations:
        surface_limit, lemma_limit = limit, 0
    elif not surfaces:
        surface_limit, lemma_limit = 0, limit
    else:
        surface_limit = (limit + 1) // 2
        lemma_limit = limit - surface_limit
    selected = [
        AuditSample(
            "unimorph_surface",
            f"unimorph_surface:{row.source_line:06d}",
            row.surface,
            normalize_audit_text(row.surface),
        )
        for row in sample_even(surfaces, surface_limit)
    ]
    selected.extend(
        AuditSample(
            "unimorph_lemma",
            f"unimorph_lemma:{row.source_line:06d}",
            row.lemma,
            normalize_audit_text(row.lemma),
        )
        for row in sample_even(segmentations, lemma_limit)
    )
    return tuple(selected)


def deduplicate_samples(samples: Iterable[AuditSample]) -> tuple[AuditSample, ...]:
    # Preserve distinct stable source IDs even when two benchmark entries use
    # the same spelling (for example a carrier and a lexical item).
    seen: set[tuple[str, str, str]] = set()
    result = []
    for sample in samples:
        key = (sample.source, sample.source_item_id, sample.text)
        if key not in seen:
            seen.add(key)
            result.append(sample)
    return tuple(result)


def hash_files(
    directory: str | Path, names: Sequence[str] = ("tokenizer.json", "tokenizer_config.json")
) -> tuple[tuple[str, str], ...]:
    root = Path(directory)
    result = []
    for name in names:
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(f"tokenizer file is missing: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        result.append((name, digest))
    return tuple(result)


def sha256_file(path: str | Path) -> str:
    """Return a stable content revision for one input file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tokenizer_snapshot(tokenizer: TokenizerLike, checkpoint: str | Path) -> TokenizerSnapshot:
    length = None
    try:
        length = len(tokenizer)  # type: ignore[arg-type]
    except TypeError:
        pass
    special = getattr(tokenizer, "all_special_tokens", ()) or ()
    return TokenizerSnapshot(
        hash_files(checkpoint),
        type(tokenizer).__name__,
        length,
        tuple(map(str, special)),
        getattr(tokenizer, "unk_token", None),
        getattr(tokenizer, "unk_token_id", None),
    )


def record_to_dict(record: TokenizationRecord) -> dict[str, Any]:
    return asdict(record)
