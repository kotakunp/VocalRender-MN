"""Fail-closed evidence registry validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from .benchmark import ValidationError

STATUSES = {"draft", "unreviewed", "reviewed", "approved", "superseded"}
ALLOWED_USES = {"hypothesis", "context_annotation", "pronunciation", "phonology", "alignment"}


def load_evidence_registry(path: str | Path) -> dict[str, Mapping[str, Any]]:
    location = Path(path)
    try:
        raw = yaml.safe_load(location.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValidationError(f"cannot read evidence registry {location}: {exc}") from exc
    if not isinstance(raw, Mapping) or not isinstance(raw.get("evidence", []), list):
        raise ValidationError("evidence registry must contain an evidence list")
    result: dict[str, Mapping[str, Any]] = {}
    for index, entry in enumerate(raw["evidence"]):
        if not isinstance(entry, Mapping):
            raise ValidationError(f"evidence[{index}] must be a mapping")
        stable_id = entry.get("id")
        if not isinstance(stable_id, str) or not stable_id.strip():
            raise ValidationError(f"evidence[{index}].id must be nonempty")
        if stable_id in result:
            raise ValidationError(f"duplicate evidence id {stable_id}")
        for field in (
            "claim",
            "source_type",
            "citation",
            "language_variety",
            "locator",
            "review_status",
        ):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValidationError(f"evidence[{index}].{field} must be nonempty")
        if entry["review_status"] not in STATUSES:
            raise ValidationError(f"evidence[{index}].review_status unsupported")
        allowed_use = entry.get("allowed_use")
        if isinstance(allowed_use, str):
            uses = {allowed_use}
        elif isinstance(allowed_use, list) and all(isinstance(value, str) for value in allowed_use):
            uses = set(allowed_use)
        else:
            raise ValidationError(f"evidence[{index}].allowed_use must be a string or list of strings")
        if not uses or not uses <= ALLOWED_USES:
            raise ValidationError(f"evidence[{index}].allowed_use unsupported")
        result[stable_id] = entry
    return result


def require_evidence(
    registry: Mapping[str, Mapping[str, Any]], ids: list[str] | tuple[str, ...], *, use: str, resolved: bool = True
) -> None:
    for stable_id in ids:
        entry = registry.get(stable_id)
        if entry is None:
            raise ValidationError(f"unknown evidence id {stable_id}")
        allowed = entry["allowed_use"]
        uses = {allowed} if isinstance(allowed, str) else set(allowed)
        if use not in uses:
            raise ValidationError(f"evidence {stable_id} does not permit use {use}")
        if resolved and entry["review_status"] not in {"approved", "reviewed"}:
            raise ValidationError(f"resolved claim {stable_id} requires reviewed evidence")
