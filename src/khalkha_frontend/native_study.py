"""Fail-closed, deterministic helpers for the native-reference study kit.

This module deliberately treats context labels and lyric boundaries as reviewed
study metadata.  It never infers either from orthography.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from .benchmark import BenchmarkManifest, ValidationError

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SUPPORTED_FIELDS = {
    "structural_context",
    "vowel_context_class",
    "cluster_or_ng_context",
    "target_consonant",
    "trigger_type",
}
ALLOWED_LABELS = {
    "structural_context": {"word_initial", "intervocalic", "preconsonantal_cluster", "word_final", "internal"},
    "vowel_context_class": {"front", "back"},
    "cluster_or_ng_context": {"ng", "cluster"},
    "trigger_type": {"explicit_soft_sign", "contextual"},
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def hash_item(item_id: str) -> str:
    return sha256_bytes(unicodedata.normalize("NFC", f"mnphon-native-v1:{item_id}").encode("utf-8"))


def _as_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be a mapping")
    return value


@dataclass(frozen=True)
class Quota:
    id: str
    group: str
    field: str
    allowed_values: tuple[str, ...]
    minimum_count: int
    required: bool
    conditions: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], index: int) -> "Quota":
        label = f"quotas[{index}]"
        values = raw.get("allowed_values")
        if isinstance(values, str):
            values = values.split("|")
        if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v for v in values):
            raise ValidationError(f"{label}.allowed_values must be a nonempty list")
        field = str(raw.get("field", ""))
        if field not in SUPPORTED_FIELDS and field != "approved_complete_contrast_pair":
            raise ValidationError(f"{label}.field unsupported: {field}")
        try:
            minimum = int(raw["minimum_count"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(f"{label}.minimum_count must be an integer") from exc
        required = bool(raw.get("required", False))
        if minimum < 0 or required and minimum == 0:
            raise ValidationError(f"{label}.minimum_count must be positive for required quotas")
        raw_conditions = raw.get("conditions", {})
        if not isinstance(raw_conditions, Mapping):
            raise ValidationError(f"{label}.conditions must be a mapping")
        conditions: list[tuple[str, str]] = []
        for condition_field, condition_value in raw_conditions.items():
            if condition_field not in SUPPORTED_FIELDS or not isinstance(condition_value, str):
                raise ValidationError(f"{label}.conditions contains an unsupported condition")
            allowed = ALLOWED_LABELS.get(condition_field)
            if allowed and condition_value not in allowed:
                raise ValidationError(f"{label}.conditions.{condition_field} has an unsupported label")
            conditions.append((condition_field, condition_value))
        return cls(
            str(raw["id"]),
            str(raw["group"]),
            field,
            tuple(values),
            minimum,
            required,
            tuple(sorted(conditions)),
        )


def load_quotas(path: Path) -> tuple[Quota, ...]:
    root = _as_mapping(yaml.safe_load(path.read_text(encoding="utf-8")) or {}, str(path))
    raw = root.get("quotas", [])
    if not isinstance(raw, list):
        raise ValidationError(f"{path}: quotas must be a list")
    quotas = tuple(Quota.from_mapping(_as_mapping(v, f"quotas[{i}]"), i) for i, v in enumerate(raw))
    if len({q.id for q in quotas}) != len(quotas):
        raise ValidationError("quotas: duplicate id")
    return quotas


@dataclass(frozen=True)
class ContextAnnotation:
    item_id: str
    structural_context: tuple[str, ...]
    vowel_context_class: tuple[str, ...]
    cluster_or_ng_context: tuple[str, ...]
    target_consonant: str | None
    trigger_type: tuple[str, ...]
    contrast_pair_id: str | None
    reviewer_pseudonym: str | None
    review_date: str | None
    review_status: str
    notes: str = ""

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], index: int) -> "ContextAnnotation":
        def labels(name: str) -> tuple[str, ...]:
            value = raw.get(name, [])
            if not isinstance(value, list) or any(not isinstance(v, str) or not v for v in value):
                raise ValidationError(f"annotations[{index}].{name} must be a list of strings")
            allowed = ALLOWED_LABELS.get(name)
            if allowed and set(value) - allowed:
                raise ValidationError(f"annotations[{index}].{name}: unsupported labels {sorted(set(value)-allowed)}")
            return tuple(value)

        return cls(
            item_id=str(raw.get("item_id", "")),
            structural_context=labels("structural_context"),
            vowel_context_class=labels("vowel_context_class"),
            cluster_or_ng_context=labels("cluster_or_ng_context"),
            target_consonant=raw.get("target_consonant"),
            trigger_type=labels("trigger_type"),
            contrast_pair_id=raw.get("contrast_pair_id"),
            reviewer_pseudonym=raw.get("reviewer_pseudonym"),
            review_date=raw.get("review_date"),
            review_status=str(raw.get("review_status", "unreviewed")),
            notes=str(raw.get("notes", "")),
        )

    @property
    def approved(self) -> bool:
        return self.review_status == "approved" and bool(self.reviewer_pseudonym and self.review_date)

    def values(self, field: str) -> tuple[str, ...]:
        if field == "target_consonant":
            return (self.target_consonant,) if self.target_consonant else ()
        return tuple(getattr(self, field))


def load_context_annotations(
    path: Path, manifest: BenchmarkManifest
) -> tuple[dict[str, ContextAnnotation], dict[str, Any]]:
    root = _as_mapping(yaml.safe_load(path.read_text(encoding="utf-8")) or {}, str(path))
    expected = str(root.get("benchmark_manifest_sha256", ""))
    if not SHA256_RE.fullmatch(expected):
        raise ValidationError("context annotations: benchmark_manifest_sha256 is required")
    if manifest.source_path is None or expected != sha256_file(manifest.source_path):
        raise ValidationError("context annotations: stale benchmark checksum")
    raw = root.get("items", [])
    if not isinstance(raw, list):
        raise ValidationError("context annotations.items must be a list")
    result: dict[str, ContextAnnotation] = {}
    known = {item.id: item for item in manifest.items}
    for index, value in enumerate(raw):
        annotation = ContextAnnotation.from_mapping(_as_mapping(value, f"items[{index}]"), index)
        if annotation.item_id not in known:
            raise ValidationError(f"context annotation references unknown item {annotation.item_id}")
        if annotation.item_id in result:
            raise ValidationError(f"duplicate context annotation {annotation.item_id}")
        if annotation.approved and annotation.target_consonant is None:
            raise ValidationError(f"approved annotation {annotation.item_id} needs target_consonant")
        result[annotation.item_id] = annotation
    pair_rows = root.get("contrast_pairs", [])
    if not isinstance(pair_rows, list):
        raise ValidationError("contrast_pairs must be a list")
    seen_pairs: set[str] = set()
    seen_members: set[str] = set()
    known_groups = {item.id: item.target_group for item in manifest.items}
    for index, pair in enumerate(pair_rows):
        pair = _as_mapping(pair, f"contrast_pairs[{index}]")
        pair_id = pair.get("pair_id")
        hard_id = pair.get("hard_item_id")
        soft_id = pair.get("soft_item_id")
        if not all(isinstance(value, str) and value for value in (pair_id, hard_id, soft_id)) or hard_id == soft_id:
            raise ValidationError(f"contrast_pairs[{index}] must name two distinct items")
        if pair_id in seen_pairs or hard_id in seen_members or soft_id in seen_members:
            raise ValidationError(f"contrast_pairs[{index}] duplicate pair or membership")
        if known_groups.get(hard_id) != "PALATALIZATION" or known_groups.get(soft_id) != "PALATALIZATION":
            raise ValidationError(f"contrast pair {pair_id} members must be PALATALIZATION items")
        if hard_id not in result or soft_id not in result:
            raise ValidationError(f"contrast pair {pair_id} members need context annotations")
        if (
            not result[hard_id].approved
            or not result[soft_id].approved
            or result[hard_id].contrast_pair_id != pair_id
            or result[soft_id].contrast_pair_id != pair_id
        ):
            raise ValidationError(f"contrast pair {pair_id} requires matching approved annotations")
        if pair.get("review_status") != "approved" or not pair.get("reviewer_pseudonym") or not pair.get("review_date"):
            raise ValidationError(f"contrast pair {pair_id} requires explicit pair approval")
        seen_pairs.add(pair_id)
        seen_members.update((hard_id, soft_id))
    return result, dict(root)


def quota_satisfied(item_ids: Iterable[str], annotations: Mapping[str, ContextAnnotation], quota: Quota) -> bool:
    selected = set(item_ids)
    values: set[str] = set()
    for item_id in selected:
        annotation = annotations.get(item_id)
        if not annotation or not annotation.approved:
            continue
        if any(value not in annotation.values(field) for field, value in quota.conditions):
            continue
        if quota.field == "approved_complete_contrast_pair":
            pair_ids = [
                candidate
                for candidate in selected
                if annotations.get(candidate) and annotations[candidate].contrast_pair_id == annotation.contrast_pair_id
            ]
            if (
                annotation.contrast_pair_id
                and ("any" in quota.allowed_values or annotation.contrast_pair_id in quota.allowed_values)
                and len(pair_ids) == 2
            ):
                values.add(annotation.contrast_pair_id)
        elif "distinct" in quota.allowed_values:
            values.update(annotation.values(quota.field))
        elif set(annotation.values(quota.field)) & set(quota.allowed_values):
            values.add(item_id)
    return len(values) >= quota.minimum_count


def quota_count(item_ids: Iterable[str], annotations: Mapping[str, ContextAnnotation], quota: Quota) -> int:
    selected = set(item_ids)
    values: set[str] = set()
    for item_id in selected:
        annotation = annotations.get(item_id)
        if not annotation or not annotation.approved:
            continue
        if any(value not in annotation.values(field) for field, value in quota.conditions):
            continue
        if quota.field == "approved_complete_contrast_pair":
            pair_ids = [
                candidate
                for candidate in selected
                if annotations.get(candidate) and annotations[candidate].contrast_pair_id == annotation.contrast_pair_id
            ]
            if (
                annotation.contrast_pair_id
                and ("any" in quota.allowed_values or annotation.contrast_pair_id in quota.allowed_values)
                and len(pair_ids) == 2
            ):
                values.add(annotation.contrast_pair_id)
        elif "distinct" in quota.allowed_values:
            values.update(annotation.values(quota.field))
        elif set(annotation.values(quota.field)) & set(quota.allowed_values):
            values.add(item_id)
    return len(values)


def diversity_vector(
    item_ids: Iterable[str], annotations: Mapping[str, ContextAnnotation], fields: Iterable[str]
) -> tuple[int, ...]:
    ids = tuple(item_ids)
    return tuple(len({value for item_id in ids for value in annotations[item_id].values(field)}) for field in fields)


def _pairs_for_group(
    annotations: Mapping[str, ContextAnnotation], group_ids: set[str], manifest: BenchmarkManifest
) -> dict[str, tuple[str, str]]:
    groups = {item.id: item.target_group for item in manifest.items}
    pair_members: dict[str, list[str]] = {}
    for item_id in group_ids:
        pair_id = annotations[item_id].contrast_pair_id
        if pair_id:
            pair_members.setdefault(pair_id, []).append(item_id)
    result = {}
    for pair_id, members in pair_members.items():
        if len(members) != 2 or any(groups.get(member) != "PALATALIZATION" for member in members):
            raise ValidationError(f"contrast pair {pair_id} must have exactly two PALATALIZATION members")
        result[pair_id] = tuple(sorted(members))  # type: ignore[assignment]
    return result


def select_group(
    group: str,
    manifest: BenchmarkManifest,
    annotations: Mapping[str, ContextAnnotation],
    quotas: tuple[Quota, ...],
    *,
    size: int = 8,
    fields: tuple[str, ...] = (),
    excluded_ids: Iterable[str] = (),
) -> dict[str, Any]:
    excluded = set(excluded_ids)
    candidate_ids = sorted(
        item.id
        for item in manifest.items
        if item.target_group == group
        and item.id not in excluded
        and item.id in annotations
        and annotations[item.id].approved
    )
    if not candidate_ids:
        return {
            "group": group,
            "selected_ids": [],
            "feasible_sets": 0,
            "diversity_vector": [],
            "tie_cohort": [],
            "blocker": "no approved context annotations",
        }
    pairs = _pairs_for_group(annotations, set(candidate_ids), manifest) if group == "PALATALIZATION" else {}
    pair_for = {member: pair for pair, members in pairs.items() for member in members}
    # Atomic units ensure a reviewed hard/soft pair is selected together.
    units: list[tuple[str, ...]] = []
    used: set[str] = set()
    for item_id in candidate_ids:
        if item_id in used:
            continue
        pair = pair_for.get(item_id)
        unit = pairs[pair] if pair else (item_id,)
        units.append(unit)
        used.update(unit)
    group_quotas = tuple(q for q in quotas if q.group == group and q.required)
    max_reported_ties = 64

    def tokens_for(ids: tuple[str, ...], quota: Quota) -> frozenset[str]:
        tokens: set[str] = set()
        for item_id in ids:
            annotation = annotations[item_id]
            if any(value not in annotation.values(field) for field, value in quota.conditions):
                continue
            if quota.field == "approved_complete_contrast_pair":
                pair_id = annotation.contrast_pair_id
                if pair_id and all(member in ids for member in pairs.get(pair_id, ())):
                    tokens.add(pair_id)
            elif "distinct" in quota.allowed_values:
                tokens.update(annotation.values(quota.field))
            elif set(annotation.values(quota.field)) & set(quota.allowed_values):
                tokens.add(item_id)
        return frozenset(tokens)

    # Dynamic programming merges subsets that have identical quota coverage
    # and diversity sets. This preserves the exact feasible-set count and
    # hash-minimal winner without enumerating O(n choose 8) leaves.
    initial_state = (
        0,
        tuple(frozenset() for _ in group_quotas),
        tuple(frozenset() for _ in fields),
    )
    states: dict[tuple[Any, ...], dict[str, Any]] = {
        initial_state: {"ways": 1, "best": (), "cohort": [()], "truncated": False}
    }

    def hash_key(ids: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(hash_item(item_id) for item_id in ids)) + tuple(sorted(ids))

    def merge_record(target: dict[str, Any], source: dict[str, Any], added: tuple[str, ...]) -> None:
        target["ways"] += source["ways"]
        candidate_best = tuple(sorted(source["best"] + added))
        if not target["best"] or hash_key(candidate_best) < hash_key(target["best"]):
            target["best"] = candidate_best
        remaining = max_reported_ties - len(target["cohort"])
        if remaining > 0:
            target["cohort"].extend(tuple(sorted(row + added)) for row in source["cohort"][:remaining])
        if source["truncated"] or source["ways"] > remaining:
            target["truncated"] = True

    for unit in units:
        next_states = {
            state: {
                "ways": record["ways"],
                "best": record["best"],
                "cohort": list(record["cohort"]),
                "truncated": record["truncated"],
            }
            for state, record in states.items()
        }
        unit_quota_tokens = tuple(tokens_for(unit, quota) for quota in group_quotas)
        unit_field_values = tuple(
            frozenset(value for item_id in unit for value in annotations[item_id].values(field)) for field in fields
        )
        for state, record in states.items():
            slots, quota_tokens, field_values = state
            if slots + len(unit) > size:
                continue
            new_state = (
                slots + len(unit),
                tuple(left | right for left, right in zip(quota_tokens, unit_quota_tokens)),
                tuple(left | right for left, right in zip(field_values, unit_field_values)),
            )
            if new_state not in next_states:
                next_states[new_state] = {"ways": 0, "best": (), "cohort": [], "truncated": False}
            merge_record(next_states[new_state], record, unit)
        states = next_states

    feasible = [
        (state, record)
        for state, record in states.items()
        if state[0] == size and all(len(tokens) >= quota.minimum_count for tokens, quota in zip(state[1], group_quotas))
    ]
    if not feasible:
        return {
            "group": group,
            "selected_ids": [],
            "feasible_sets": 0,
            "diversity_vector": [],
            "tie_cohort": [],
            "blocker": "required quota infeasible",
        }
    best_vector = max(tuple(len(values) for values in state[2]) for state, _ in feasible)
    best_states = [(state, record) for state, record in feasible if tuple(len(v) for v in state[2]) == best_vector]
    feasible_count = sum(record["ways"] for _, record in feasible)
    tie_count = sum(record["ways"] for _, record in best_states)
    winner = min((record["best"] for _, record in best_states), key=hash_key)
    cohort = sorted({ids for _, record in best_states for ids in record["cohort"]}, key=hash_key)[:max_reported_ties]
    cohort_truncated = tie_count > len(cohort) or any(record["truncated"] for _, record in best_states)
    return {
        "group": group,
        "selected_ids": list(winner),
        "feasible_sets": feasible_count,
        "diversity_vector": list(best_vector),
        "tie_cohort": [list(ids) for ids in cohort],
        "tie_cohort_count": tie_count,
        "tie_cohort_truncated": cohort_truncated,
        "tie_break_hashes": [hash_item(item_id) for item_id in winner] if tie_count > 1 else None,
    }


def validate_source_span(source_text: str, units: list[Mapping[str, Any]]) -> None:
    normalized = unicodedata.normalize("NFC", source_text)
    if normalized != source_text or not units:
        raise ValidationError("alignment source_text must be NFC and units must be nonempty")
    cursor = 0
    for index, unit in enumerate(units):
        span = unit.get("source_span")
        if (
            not isinstance(span, list)
            or len(span) != 2
            or span[0] != cursor
            or not isinstance(span[1], int)
            or span[1] <= span[0]
        ):
            raise ValidationError(f"alignment unit {index}: spans must be contiguous and nonempty")
        if unit.get("text") != source_text[span[0] : span[1]]:
            raise ValidationError(f"alignment unit {index}: text does not match source span")
        cursor = span[1]
    if cursor != len(source_text):
        raise ValidationError("alignment spans must reconstruct source_text")
