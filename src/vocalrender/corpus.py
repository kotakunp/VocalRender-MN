# flake8: noqa: E501
"""Fail-closed corpus eligibility and leakage-safe split utilities.

This module deliberately treats a manifest as an evidence ledger, not as proof
of rights.  An item is eligible only when all required identity, checksum,
path, score, consent, rights, and review fields are explicit and approved.
Unknown or missing evidence is reported as an exclusion reason.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


class CorpusError(ValueError):
    """Raised for malformed manifests or a detected leakage policy violation."""


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_PII_KEYS = {
    "name",
    "real_name",
    "full_name",
    "email",
    "phone",
    "telephone",
    "address",
    "person_name",
    "speaker_name",
    "singer_name",
}
_ALLOWED = {"allowed", "approved"}
_SINGING_TYPES = {"singing", "sung", "singer", "singing_voice", "native_singing"}
_MONGOLIAN_LANGUAGES = {"mn", "mongolian", "khk"}
_STANDARD_KHALKHA = {"standard_khalkha", "standard-khalkha", "khalkha", "khk"}
_EXCLUDED_SOURCE_MARKERS = {"mn-phon-32", "music3", "synthetic_music3"}


@dataclass(frozen=True)
class CorpusItem:
    """Normalized, non-sensitive manifest item."""

    item_id: str
    source_id: str
    audio_path: str
    score_path: str
    audio_sha256: str
    score_sha256: str
    duration_seconds: float
    language: str
    variety: str
    vocal_type: str
    singer_group: str
    song_group: str
    session_group: str
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class Exclusion:
    item_id: str
    reason: str


@dataclass(frozen=True)
class CorpusReport:
    manifest_path: str
    eligible: tuple[CorpusItem, ...]
    excluded: tuple[Exclusion, ...]
    errors: tuple[str, ...]

    @property
    def eligible_duration_seconds(self) -> float:
        return sum(item.duration_seconds for item in self.eligible)

    @property
    def excluded_reasons(self) -> dict[str, int]:
        return dict(Counter(item.reason for item in self.excluded))

    def summary(self) -> dict[str, Any]:
        return {
            "eligible_items": len(self.eligible),
            "eligible_duration_seconds": round(self.eligible_duration_seconds, 6),
            "eligible_hours": round(self.eligible_duration_seconds / 3600, 6),
            "excluded_items": len(self.excluded),
            "excluded_reasons": self.excluded_reasons,
            "errors": list(self.errors),
        }


def repository_root_for(path: Path) -> Path:
    """Find the checkout root for a manifest without using the cwd."""

    path = path.resolve()
    for candidate in (path.parent, *path.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return path.parent


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CorpusError(f"{label} must be a mapping")
    return value


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise CorpusError(f"{label} must be a pseudonymous identifier")
    return value


def _relative_path(value: Any, label: str, root: Path, *, require_exists: bool = True) -> str:
    if not isinstance(value, str) or not value or "\\" in value or Path(value).is_absolute():
        raise CorpusError(f"{label} must be a repository-relative POSIX path")
    candidate = (root / Path(value)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise CorpusError(f"{label} escapes the repository root") from exc
    if require_exists and not candidate.is_file():
        raise CorpusError(f"{label} does not resolve to a file")
    return Path(value).as_posix()


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise CorpusError(f"{label} must be a 64-character SHA-256 checksum")
    return value.lower()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _interval(value: Any, label: str) -> tuple[float, float]:
    if isinstance(value, Mapping):
        start, end = value.get("start_seconds", value.get("start")), value.get("end_seconds", value.get("end"))
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        start, end = value
    else:
        raise CorpusError(f"{label} must contain start/end seconds")
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or start < 0 or end <= start:
        raise CorpusError(f"{label} must be a non-empty non-negative interval")
    return float(start), float(end)


def _contains_pii_key(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in _PII_KEYS:
                return str(key)
            result = _contains_pii_key(child)
            if result:
                return result
    elif isinstance(value, list):
        for child in value:
            result = _contains_pii_key(child)
            if result:
                return result
    return None


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load and minimally validate a YAML corpus manifest."""

    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise CorpusError(f"cannot read manifest: {exc}") from exc
    if not isinstance(raw, dict):
        raise CorpusError("manifest must contain a top-level mapping")
    if raw.get("schema_version") != 1:
        raise CorpusError("unsupported or missing schema_version (expected 1)")
    items = raw.get("items", [])
    if not isinstance(items, list):
        raise CorpusError("items must be a list")
    pii_key = _contains_pii_key(raw)
    if pii_key:
        raise CorpusError(f"manifest contains prohibited personal-data field '{pii_key}'")
    return raw


def _rights(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = raw.get("rights")
    if nested is not None:
        return _mapping(nested, "rights")
    return raw


def _right_is_allowed(raw: Mapping[str, Any], key: str) -> bool:
    value = _rights(raw).get(key)
    top_value = raw.get(key)
    if top_value is not None and value is not None and top_value != value:
        return False
    return isinstance(value, str) and value.lower() in _ALLOWED


def _has_revocation(raw: Mapping[str, Any]) -> bool:
    """Reject explicit revocation/expiry markers wherever rights are recorded."""

    if raw.get("revoked") is True or raw.get("expired") is True:
        return True
    for child in (raw, raw.get("rights"), raw.get("license")):
        if isinstance(child, Mapping):
            status = child.get("status")
            if isinstance(status, str) and status.lower() in {"revoked", "expired", "non-releasable"}:
                return True
    return False


def _consent_is_valid(raw: Mapping[str, Any]) -> bool:
    value = raw.get("consent_ref", _rights(raw).get("consent_ref"))
    return (
        isinstance(value, str)
        and bool(_ID_RE.fullmatch(value))
        and not value.lower().startswith(("http", "file", "mailto"))
    )


def _normalized_item(raw: Mapping[str, Any], root: Path) -> CorpusItem:
    item_id = _id(raw.get("id", raw.get("item_id")), "item id")
    source_id = _id(raw.get("source_id"), f"{item_id}.source_id")
    audio_path = _relative_path(raw.get("audio_path"), f"{item_id}.audio_path", root)
    score_path = _relative_path(raw.get("score_path"), f"{item_id}.score_path", root)
    checksum = _sha256(raw.get("audio_sha256"), f"{item_id}.audio_sha256")
    actual_checksum = _file_sha256(root / Path(audio_path))
    if actual_checksum != checksum:
        raise CorpusError(f"{item_id}.audio_sha256 does not match audio_path")
    score_checksum = _sha256(raw.get("score_sha256"), f"{item_id}.score_sha256")
    actual_score_checksum = _file_sha256(root / Path(score_path))
    if actual_score_checksum != score_checksum:
        raise CorpusError(f"{item_id}.score_sha256 does not match score_path")
    duration = raw.get("duration_seconds")
    if not isinstance(duration, (int, float)) or duration <= 0:
        raise CorpusError(f"{item_id}.duration_seconds must be positive")
    language = str(raw.get("language", "")).lower()
    variety = str(raw.get("variety", "")).lower()
    vocal_type = str(raw.get("vocal_type", "")).lower()
    groups = raw.get("groups", raw)
    groups = _mapping(groups, f"{item_id}.groups")
    singer = _id(groups.get("singer_group", raw.get("singer_group")), f"{item_id}.singer_group")
    song = _id(groups.get("song_group", raw.get("song_group")), f"{item_id}.song_group")
    session = _id(groups.get("session_group", raw.get("session_group")), f"{item_id}.session_group")
    return CorpusItem(
        item_id,
        source_id,
        audio_path,
        score_path,
        checksum,
        score_checksum,
        float(duration),
        language,
        variety,
        vocal_type,
        singer,
        song,
        session,
        raw,
    )


def _source_excluded(source_id: str) -> bool:
    normalized = source_id.lower().replace("_", "-")
    return any(marker in normalized for marker in _EXCLUDED_SOURCE_MARKERS)


def validate_manifest(path: str | Path, *, repository_root: Path | None = None) -> CorpusReport:
    """Return eligible items and safe exclusion reasons; fail on structural errors."""

    manifest_path = Path(path)
    raw = load_manifest(manifest_path)
    root = (repository_root or repository_root_for(manifest_path)).resolve()
    eligible: list[CorpusItem] = []
    excluded: list[Exclusion] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    checksum_items: defaultdict[str, list[str]] = defaultdict(list)
    for index, value in enumerate(raw["items"]):
        if not isinstance(value, Mapping):
            raise CorpusError(f"items[{index}] must be a mapping")
        raw_id = value.get("id", value.get("item_id", f"item-{index}"))
        item_id = raw_id if isinstance(raw_id, str) else f"item-{index}"
        if item_id in seen_ids:
            raise CorpusError(f"duplicate item id '{item_id}'")
        seen_ids.add(item_id)
        try:
            item = _normalized_item(value, root)
        except CorpusError as exc:
            excluded.append(Exclusion(item_id, f"invalid:{exc}"))
            continue
        checksum_items[item.audio_sha256].append(item.item_id)
        reasons: list[str] = []
        if _source_excluded(item.source_id):
            reasons.append("excluded_source")
        if item.language not in _MONGOLIAN_LANGUAGES:
            reasons.append("not_mongolian")
        if item.variety not in _STANDARD_KHALKHA:
            reasons.append("not_standard_khalkha")
        if item.vocal_type not in _SINGING_TYPES:
            reasons.append("not_singing")
        for key in ("redistribution", "research_evaluation_use", "training_use", "derivative_model_permission"):
            if not _right_is_allowed(value, key):
                reasons.append(f"rights_{key}_not_allowed")
        license_info = value.get("license")
        if not (
            isinstance(license_info, str)
            and license_info
            or isinstance(license_info, Mapping)
            and isinstance(license_info.get("identifier"), str)
            and license_info.get("identifier")
        ):
            reasons.append("license_missing_or_invalid")
        review = _rights(value).get("review_status", value.get("review_status"))
        if not isinstance(review, str) or review.lower() != "approved":
            reasons.append("review_not_approved")
        if not _consent_is_valid(value):
            reasons.append("consent_missing_or_invalid")
        if _has_revocation(value):
            reasons.append("rights_revoked_or_expired")
        if reasons:
            excluded.extend(Exclusion(item.item_id, reason) for reason in reasons)
        else:
            eligible.append(item)
    for checksum, ids in checksum_items.items():
        if len(ids) > 1:
            duplicate_ids = set(ids)
            eligible = [item for item in eligible if item.item_id not in duplicate_ids]
            excluded.extend(Exclusion(item_id, "duplicate_audio_sha256") for item_id in ids)
    _validate_intervals_and_prompts(raw["items"], eligible, errors, root=root)
    return CorpusReport(str(manifest_path), tuple(eligible), tuple(excluded), tuple(errors))


def _raw_interval(raw: Mapping[str, Any], key: str) -> tuple[float, float] | None:
    value = raw.get(key)
    return _interval(value, key) if value is not None else None


def _validate_intervals_and_prompts(
    raw_items: Iterable[Any], eligible: Iterable[CorpusItem], errors: list[str], *, root: Path | None = None
) -> None:
    eligible_by_id = {item.item_id: item for item in eligible}
    for item in eligible_by_id.values():
        raw = item.raw
        target = _raw_interval(raw, "target_interval")
        prompt = raw.get("prompt")
        if prompt is None:
            continue
        prompt_map = _mapping(prompt, f"{item.item_id}.prompt")
        p_interval = _interval(prompt_map, f"{item.item_id}.prompt")
        prompt_audio = prompt_map.get("audio_path", item.audio_path)
        if not isinstance(prompt_audio, str):
            errors.append(f"{item.item_id}: prompt audio_path must be a path")
            continue
        if prompt_audio != item.audio_path:
            try:
                _relative_path(
                    prompt_audio,
                    f"{item.item_id}.prompt.audio_path",
                    root or Path.cwd(),
                )
            except CorpusError as exc:
                errors.append(f"{item.item_id}: {exc}")
        if (
            prompt_audio == item.audio_path
            and target
            and not (p_interval[1] <= target[0] or p_interval[0] >= target[1])
        ):
            errors.append(f"{item.item_id}: prompt-target intervals overlap")
        prompt_item_id = prompt_map.get("item_id")
        if prompt_item_id is not None and prompt_item_id not in eligible_by_id:
            errors.append(f"{item.item_id}: prompt references ineligible or unknown item")


def _component_groups(items: list[CorpusItem]) -> list[list[CorpusItem]]:
    parent = list(range(len(items)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    first: dict[tuple[str, str], int] = {}
    for index, item in enumerate(items):
        for key, value in (("singer", item.singer_group), ("song", item.song_group), ("session", item.session_group)):
            marker = (key, value)
            if marker in first:
                union(index, first[marker])
            else:
                first[marker] = index
    groups: defaultdict[int, list[CorpusItem]] = defaultdict(list)
    for index, item in enumerate(items):
        groups[find(index)].append(item)
    return list(groups.values())


def _bucket(group_key: str) -> int:
    digest = hashlib.sha256(group_key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % 100


def generate_splits(report: CorpusReport, *, manifest_sha256: str, seed: str = "mn-svs-v1") -> dict[str, Any]:
    """Create deterministic group-disjoint train/validation/test assignments."""

    if report.errors:
        raise CorpusError("; ".join(report.errors))
    if not report.eligible:
        raise CorpusError("zero eligible native Standard Khalkha singing items")
    assignments: dict[str, str] = {}
    groups = _component_groups(list(report.eligible))
    for group in groups:
        key = "|".join(sorted(item.item_id for item in group)) + "|" + seed
        bucket = _bucket(key)
        split = "test" if bucket < 20 else "validation" if bucket < 40 else "train"
        for item in group:
            assignments[item.item_id] = split
    audio_to_item = {item.audio_path: item.item_id for item in report.eligible}
    for item in report.eligible:
        raw_prompt = item.raw.get("prompt")
        if assignments[item.item_id] == "test" and isinstance(raw_prompt, Mapping):
            prompt_id = raw_prompt.get("item_id") or audio_to_item.get(raw_prompt.get("audio_path", item.audio_path))
            if prompt_id and assignments.get(prompt_id) == "train":
                raise CorpusError(f"test target {item.item_id} uses train audio as prompt")
    split_items = {
        name: sorted([item_id for item_id, split in assignments.items() if split == name])
        for name in ("train", "validation", "test")
    }
    return {
        "schema_version": 1,
        "split_version": hashlib.sha256((manifest_sha256 + seed).encode("utf-8")).hexdigest()[:16],
        "manifest_sha256": manifest_sha256,
        "seed": seed,
        "policy": {
            "test_song_disjoint": True,
            "test_singer_disjoint": True,
            "test_session_disjoint": True,
            "validation_song_disjoint": True,
        },
        "splits": split_items,
        "prompt_intervals": {
            item.item_id: item.raw["prompt"] for item in report.eligible if item.raw.get("prompt") is not None
        },
    }


def verify_splits(report: CorpusReport, splits: Mapping[str, Any]) -> None:
    """Verify split membership, group disjointness, and prompt policies."""

    split_map: dict[str, str] = {}
    for split in ("train", "validation", "test"):
        ids = splits.get("splits", {}).get(split, [])
        if not isinstance(ids, list):
            raise CorpusError(f"split '{split}' must be a list")
        for item_id in ids:
            if item_id in split_map:
                raise CorpusError(f"item {item_id} appears in multiple splits")
            split_map[item_id] = split
    expected = {item.item_id for item in report.eligible}
    if set(split_map) != expected:
        raise CorpusError("split manifest does not cover exactly the eligible items")
    by_split = {
        split: [item for item in report.eligible if split_map[item.item_id] == split]
        for split in ("train", "validation", "test")
    }
    for left_name, right_name, fields in (
        ("train", "validation", ("song_group",)),
        ("train", "test", ("song_group", "singer_group", "session_group")),
        ("validation", "test", ("song_group",)),
    ):
        for field in fields:
            left = {getattr(item, field) for item in by_split[left_name]}
            right = {getattr(item, field) for item in by_split[right_name]}
            if left & right:
                raise CorpusError(f"{field} overlap between {left_name} and {right_name}")
    audio_to_item = {item.audio_path: item.item_id for item in report.eligible}
    for item in report.eligible:
        raw_prompt = item.raw.get("prompt")
        if split_map[item.item_id] == "test" and isinstance(raw_prompt, Mapping):
            prompt_id = raw_prompt.get("item_id") or audio_to_item.get(raw_prompt.get("audio_path", item.audio_path))
            if prompt_id and split_map.get(prompt_id) == "train":
                raise CorpusError(f"test target {item.item_id} uses train audio as prompt")
    errors: list[str] = []
    _validate_intervals_and_prompts(
        [item.raw for item in report.eligible],
        report.eligible,
        errors,
        root=repository_root_for(Path(report.manifest_path)),
    )
    if errors:
        raise CorpusError("; ".join(errors))


def manifest_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_yaml(path: str | Path, value: Mapping[str, Any]) -> None:
    Path(path).write_text(yaml.safe_dump(dict(value), sort_keys=False, allow_unicode=True), encoding="utf-8")


def json_summary(report: CorpusReport) -> str:
    return json.dumps(report.summary(), ensure_ascii=False, sort_keys=True)
