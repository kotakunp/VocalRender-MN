"""Canonical MN-PHON-250 manifest types and validation."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping
import re

import yaml

from .types import EvidenceRef


class ValidationError(ValueError):
    """Raised when a benchmark or related manifest violates its schema."""


class Lexicality(str, Enum):
    CARRIER = "carrier"
    LEXICAL = "lexical"
    CONTRAST = "contrast"
    UNKNOWN = "unknown"


class EvaluationStatus(str, Enum):
    UNTESTED = "untested"
    IN_PROGRESS = "in_progress"
    EVALUATED = "evaluated"
    NEEDS_REVIEW = "needs_review"


class AudioSource(str, Enum):
    NATIVE_SPEECH = "native_speech"
    NATIVE_SINGING = "native_singing"
    BENCHMARK_TTS = "benchmark_tts"
    MUSIC3 = "music3"


_PROVENANCE_MARKER_SEGMENTS = {"_" * 2 + "GET" + "_" * 2, "_" * 2 + "MAKE" + "_" * 2}
_SOURCE_ROOTS = {
    AudioSource.NATIVE_SPEECH: PurePosixPath("data/raw/native_speech"),
    AudioSource.NATIVE_SINGING: PurePosixPath("data/raw/native_singing"),
    AudioSource.BENCHMARK_TTS: PurePosixPath("data/raw/benchmark_tts"),
    AudioSource.MUSIC3: PurePosixPath("data/raw/music3"),
}
_EXPECTED_EVIDENCE_KINDS = {
    "linguistic_literature",
    "native_speech",
    "native_singing",
    "native_speaker_validation",
}


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be a mapping")
    return value


def _evidence(values: Any, label: str) -> tuple[EvidenceRef, ...]:
    if values in (None, []):
        return ()
    if not isinstance(values, list):
        raise ValidationError(f"{label}.evidence must be a list")
    result = []
    for index, raw in enumerate(values):
        entry = _mapping(raw, f"{label}.evidence[{index}]")
        source = entry.get("source") or entry.get("source_url") or entry.get("local_path")
        if (
            not isinstance(entry.get("id"), str)
            or not entry["id"].strip()
            or not isinstance(source, str)
            or not source.strip()
        ):
            raise ValidationError(f"{label}.evidence[{index}] needs id and source")
        result.append(
            EvidenceRef(
                id=str(entry["id"]),
                source=str(source),
                kind=str(entry.get("kind", "")),
                reviewer=entry.get("reviewer"),
                status=str(entry.get("status", "unreviewed")),
                date=entry.get("date"),
                notes=str(entry.get("notes", "")),
            )
        )
    return tuple(result)


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


@dataclass(frozen=True)
class BenchmarkItem:
    id: str
    number: int
    text: str
    target_group: str
    legacy_category: str
    lexicality: Lexicality
    context: str | None = None
    position: str | None = None
    target_grapheme: str | None = None
    left_context: str | None = None
    right_context: str | None = None
    expected_phoneme: str | None = None
    expected_phone: str | None = None
    evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    status: EvaluationStatus = EvaluationStatus.UNTESTED
    notes: str = ""

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], index: int) -> "BenchmarkItem":
        label = f"items[{index}]"
        item = _mapping(raw, label)
        try:
            lexicality = Lexicality(str(item["lexicality"]))
            status = EvaluationStatus(str(item.get("status", "untested")))
        except (KeyError, ValueError) as exc:
            raise ValidationError(f"{label}: invalid lexicality/status: {exc}") from exc
        try:
            result = cls(
                id=str(item["id"]),
                number=int(item["number"]),
                text=str(item["text"]),
                target_group=str(item["target_group"]),
                legacy_category=str(item["legacy_category"]),
                lexicality=lexicality,
                context=_optional_str(item.get("context")),
                position=_optional_str(item.get("position")),
                target_grapheme=_optional_str(item.get("target_grapheme")),
                left_context=_optional_str(item.get("left_context")),
                right_context=_optional_str(item.get("right_context")),
                expected_phoneme=_optional_str(item.get("expected_phoneme")),
                expected_phone=_optional_str(item.get("expected_phone")),
                evidence=_evidence(item.get("evidence", []), label),
                status=status,
                notes=str(item.get("notes", "")),
            )
        except KeyError as exc:
            raise ValidationError(f"{label}: missing required field {exc.args[0]}") from exc
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{label}: {exc}") from exc
        result.validate(label)
        return result

    def validate(self, label: str = "item") -> None:
        expected_id = f"MNPHON_{self.number:03d}"
        if self.id != expected_id:
            raise ValidationError(f"{label}.id: expected {expected_id}, got {self.id}")
        if not self.text or unicodedata.normalize("NFC", self.text) != self.text:
            raise ValidationError(f"{label}.text: must be non-empty NFC-normalized text")
        if self.target_group not in {"L", "G", "H", "PALATALIZATION"}:
            raise ValidationError(f"{label}.target_group: unsupported group {self.target_group}")
        if (self.expected_phoneme is not None or self.expected_phone is not None) and not self.evidence:
            raise ValidationError(f"{label}: expected phoneme/phone requires evidence")
        if self.expected_phoneme is not None or self.expected_phone is not None:
            kinds = {evidence.kind.strip().lower().replace(" ", "_").replace("-", "_") for evidence in self.evidence}
            if not kinds & _EXPECTED_EVIDENCE_KINDS:
                raise ValidationError(f"{label}: expected phoneme/phone evidence kind is not allowed")


@dataclass(frozen=True)
class AudioTake:
    id: str
    item_id: str
    source: AudioSource
    run_id: str
    path: str
    provider: str | None = None
    speaker_pseudonym: str | None = None
    prompt_provenance: str | None = None
    checksum: str | None = None
    system_id: str | None = None
    model_id: str | None = None
    score_checksum: str | None = None
    config_checksum: str | None = None
    alignment_checksum: str | None = None
    prompt_pseudonym: str | None = None
    generation_seed: int | None = None
    inference_run_id: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
    duration_seconds: float | None = None
    consent_reference: str | None = None
    blind_label: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        for field_name in ("id", "item_id", "run_id", "path"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"take.{field_name}: must be non-empty")
        try:
            source = AudioSource(self.source)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"take.source: invalid audio source {self.source!r}") from exc
        object.__setattr__(self, "source", source)
        self.validate()

    @property
    def relative_path(self) -> str:
        """Compatibility alias emphasizing that ``path`` is repository-relative."""

        return self.path

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], index: int) -> "AudioTake":
        label = f"takes[{index}]"
        item = _mapping(raw, label)
        for field_name in ("id", "item_id", "run_id", "path"):
            if not isinstance(item.get(field_name), str) or not item[field_name].strip():
                raise ValidationError(f"{label}.{field_name}: must be non-empty")
        try:
            result = cls(
                id=str(item["id"]),
                item_id=str(item["item_id"]),
                source=AudioSource(str(item["source"])),
                run_id=str(item["run_id"]),
                path=str(item["path"]),
                provider=_optional_str(item.get("provider")),
                speaker_pseudonym=_optional_str(item.get("speaker_pseudonym")),
                prompt_provenance=_optional_str(item.get("prompt_provenance")),
                checksum=_optional_str(item.get("checksum")),
                system_id=_optional_str(item.get("system_id")),
                model_id=_optional_str(item.get("model_id", item.get("base_checkpoint_id"))),
                score_checksum=_optional_str(item.get("score_checksum")),
                config_checksum=_optional_str(item.get("config_checksum")),
                alignment_checksum=_optional_str(item.get("alignment_checksum")),
                prompt_pseudonym=_optional_str(item.get("prompt_pseudonym")),
                generation_seed=item.get("generation_seed"),
                inference_run_id=_optional_str(item.get("inference_run_id")),
                sample_rate=item.get("sample_rate"),
                channels=item.get("channels"),
                duration_seconds=item.get("duration_seconds", item.get("duration")),
                consent_reference=_optional_str(item.get("consent_reference")),
                blind_label=_optional_str(item.get("blind_label")),
                notes=str(item.get("notes", "")),
            )
        except KeyError as exc:
            raise ValidationError(f"{label}: missing required field {exc.args[0]}") from exc
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{label}: {exc}") from exc
        result.validate_path(label)
        return result

    def validate_path(self, label: str = "take") -> None:
        if "\\" in self.path or not self.path or self.path.startswith("/"):
            raise ValidationError(f"{label}.path: must be a relative forward-slash path")
        parsed = PurePosixPath(self.path)
        if ".." in parsed.parts or any(
            any(part.startswith(prefix) for prefix in _PROVENANCE_MARKER_SEGMENTS) for part in parsed.parts
        ):
            raise ValidationError(f"{label}.path: traversal and provenance marker segments are forbidden")
        root = _SOURCE_ROOTS[self.source]
        if not (parsed == root or root in parsed.parents):
            raise ValidationError(f"{label}.path: {self.source.value} must live beneath {root.as_posix()}")

    def validate(self, label: str = "take") -> None:
        if not self.id.strip() or not self.item_id.strip() or not self.run_id.strip() or not self.path.strip():
            raise ValidationError(f"{label}: required fields must be non-empty")
        self.validate_path(label)
        for field_name in ("checksum", "score_checksum", "config_checksum", "alignment_checksum"):
            value = getattr(self, field_name)
            if value is not None and not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValidationError(f"{label}.{field_name}: must be lowercase SHA-256")
        if self.generation_seed is not None and (
            isinstance(self.generation_seed, bool) or not isinstance(self.generation_seed, int)
        ):
            raise ValidationError(f"{label}.generation_seed: must be an integer")
        if self.sample_rate is not None and (
            isinstance(self.sample_rate, bool) or not isinstance(self.sample_rate, int) or self.sample_rate <= 0
        ):
            raise ValidationError(f"{label}.sample_rate: must be positive")
        if self.channels is not None and self.channels not in (1, 2):
            raise ValidationError(f"{label}.channels: must be 1 or 2")
        if self.duration_seconds is not None and (
            isinstance(self.duration_seconds, bool)
            or not isinstance(self.duration_seconds, (int, float))
            or self.duration_seconds <= 0
        ):
            raise ValidationError(f"{label}.duration_seconds: must be positive")
        if self.source is AudioSource.NATIVE_SINGING:
            required = {
                "score_checksum": self.score_checksum,
                "alignment_checksum": self.alignment_checksum,
                "consent_reference": self.consent_reference,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValidationError(f"{label}: native singing requires {', '.join(missing)}")
        if self.source is AudioSource.BENCHMARK_TTS:
            required = {
                "system_id": self.system_id,
                "model_id": self.model_id,
                "score_checksum": self.score_checksum,
                "config_checksum": self.config_checksum,
                "prompt_pseudonym": self.prompt_pseudonym,
                "generation_seed": self.generation_seed,
                "inference_run_id": self.inference_run_id,
            }
            missing = [name for name, value in required.items() if value is None or value == ""]
            if missing:
                raise ValidationError(f"{label}: generated take requires {', '.join(missing)}")


@dataclass(frozen=True)
class ManualRating:
    id: str
    item_id: str
    audio_take_id: str
    score: int
    rater_pseudonym: str
    timestamp: str
    confidence: str | None = None
    criterion: str | None = None
    blind_label: str | None = None
    session_id: str | None = None
    presentation_order: int | None = None
    rater_language_qualification: str | None = None
    protocol_version: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        for field_name in ("id", "item_id", "audio_take_id", "rater_pseudonym", "timestamp"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"rating.{field_name}: must be non-empty")
        self.validate()

    def validate(self, label: str = "rating") -> None:
        if type(self.score) is not int or self.score not in {0, 1, 2}:
            raise ValidationError(f"{label}.score: must be integer 0, 1, or 2")
        if self.presentation_order is not None and (
            isinstance(self.presentation_order, bool)
            or not isinstance(self.presentation_order, int)
            or self.presentation_order < 0
        ):
            raise ValidationError(f"{label}.presentation_order: must be a nonnegative integer")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], index: int) -> "ManualRating":
        label = f"ratings[{index}]"
        item = _mapping(raw, label)
        for field_name in ("id", "item_id", "audio_take_id", "rater_pseudonym", "timestamp"):
            value = item.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{label}.{field_name}: must be non-empty")
        try:
            result = cls(
                id=str(item["id"]),
                item_id=str(item["item_id"]),
                audio_take_id=str(item["audio_take_id"]),
                score=item["score"],
                rater_pseudonym=str(item["rater_pseudonym"]),
                timestamp=str(item["timestamp"]),
                confidence=_optional_str(item.get("confidence")),
                criterion=_optional_str(item.get("criterion")),
                blind_label=_optional_str(item.get("blind_label")),
                session_id=_optional_str(item.get("session_id")),
                presentation_order=item.get("presentation_order"),
                rater_language_qualification=_optional_str(item.get("rater_language_qualification")),
                protocol_version=_optional_str(item.get("protocol_version")),
                notes=str(item.get("notes", "")),
            )
        except KeyError as exc:
            raise ValidationError(f"{label}: missing required field {exc.args[0]}") from exc
        return result


@dataclass(frozen=True)
class BenchmarkManifest:
    schema_version: int
    benchmark: Mapping[str, Any]
    items: tuple[BenchmarkItem, ...]
    source_path: Path | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], source_path: Path | None = None) -> "BenchmarkManifest":
        root = _mapping(raw, "manifest")
        try:
            schema_version = int(root.get("schema_version", 0))
        except (TypeError, ValueError) as exc:
            raise ValidationError("manifest.schema_version must be an integer") from exc
        if schema_version != 2:
            raise ValidationError("manifest.schema_version: expected 2")
        benchmark = _mapping(root.get("benchmark"), "benchmark")
        raw_items = root.get("items")
        if not isinstance(raw_items, list):
            raise ValidationError("manifest.items must be a list")
        items = tuple(BenchmarkItem.from_mapping(item, index) for index, item in enumerate(raw_items))
        result = cls(schema_version, benchmark, items, source_path)
        result.validate()
        return result

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BenchmarkManifest":
        location = Path(path)
        try:
            raw = yaml.safe_load(location.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ValidationError(f"cannot read {location}: {exc}") from exc
        return cls.from_mapping(raw, location)

    def validate(self) -> None:
        try:
            count = int(self.benchmark.get("item_count", -1))
        except (TypeError, ValueError) as exc:
            raise ValidationError("benchmark.item_count must be an integer") from exc
        if count != len(self.items):
            raise ValidationError(f"benchmark.item_count={count} but found {len(self.items)} items")
        if len(self.items) != 250:
            raise ValidationError(f"benchmark must contain 250 items, found {len(self.items)}")
        expected_numbers = list(range(1, 251))
        numbers = [item.number for item in self.items]
        if numbers != expected_numbers:
            raise ValidationError("items.number: expected contiguous sequence 1..250")
        if len({item.id for item in self.items}) != len(self.items):
            raise ValidationError("items.id: duplicate item id")


def _load_list(path: Path, key: str) -> list[Mapping[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValidationError(f"cannot read {path}: {exc}") from exc
    values = _mapping(raw, str(path)).get(key, [])
    if not isinstance(values, list):
        raise ValidationError(f"{path}: {key} must be a list")
    return values


def load_audio_takes(path: str | Path) -> tuple[AudioTake, ...]:
    location = Path(path)
    return tuple(AudioTake.from_mapping(raw, index) for index, raw in enumerate(_load_list(location, "takes")))


def load_ratings(path: str | Path) -> tuple[ManualRating, ...]:
    location = Path(path)
    return tuple(ManualRating.from_mapping(raw, index) for index, raw in enumerate(_load_list(location, "ratings")))


def validate_related(
    manifest: BenchmarkManifest,
    takes: Iterable[AudioTake] = (),
    ratings: Iterable[ManualRating] = (),
    *,
    strict_files: bool = False,
    repository_root: Path | None = None,
) -> list[str]:
    """Validate related manifests, returning non-fatal missing-file warnings."""

    item_ids = {item.id for item in manifest.items}
    take_list = tuple(takes)
    take_ids: set[str] = set()
    take_blind_labels: set[str] = set()
    warnings: list[str] = []
    for take in take_list:
        take.validate()
        if take.id in take_ids:
            raise ValidationError(f"takes.{take.id}: duplicate take id")
        take_ids.add(take.id)
        if take.blind_label is not None:
            if take.blind_label in take_blind_labels:
                raise ValidationError(f"takes.{take.id}: duplicate blind label")
            take_blind_labels.add(take.blind_label)
        if take.item_id not in item_ids:
            raise ValidationError(f"takes.{take.id}.item_id: unknown item {take.item_id}")
        if repository_root is not None:
            file_path = repository_root / Path(*PurePosixPath(take.path).parts)
            if not file_path.is_file():
                message = f"takes.{take.id}.path: missing audio file {take.path}"
                if strict_files:
                    raise ValidationError(message)
                warnings.append(message)
    rating_ids: set[str] = set()
    rating_keys: set[tuple[str, str, str]] = set()
    for rating in ratings:
        rating.validate()
        if rating.id in rating_ids:
            raise ValidationError(f"ratings.{rating.id}: duplicate rating id")
        rating_ids.add(rating.id)
        if rating.criterion is not None:
            key = (rating.audio_take_id, rating.criterion, rating.rater_pseudonym)
            if key in rating_keys:
                raise ValidationError(f"ratings.{rating.id}: duplicate audio/criterion/rater key")
            rating_keys.add(key)
        if rating.item_id not in item_ids:
            raise ValidationError(f"ratings.{rating.id}.item_id: unknown item {rating.item_id}")
        if rating.audio_take_id not in take_ids:
            raise ValidationError(f"ratings.{rating.id}.audio_take_id: unknown take {rating.audio_take_id}")
        take = next(take for take in take_list if take.id == rating.audio_take_id)
        if rating.item_id != take.item_id:
            raise ValidationError(
                f"ratings.{rating.id}.item_id: {rating.item_id} disagrees with take {take.id} item {take.item_id}"
            )
        if rating.blind_label is not None and rating.audio_take_id == rating.blind_label:
            raise ValidationError(f"ratings.{rating.id}: rater-facing row must not expose take ID")
    return warnings


def derive_traffic_light(ratings: Iterable[ManualRating], min_count: int = 2) -> str:
    """Derive a conservative view; it is never persisted as benchmark truth."""

    if min_count < 1:
        raise ValueError("min_count must be at least 1")
    values = tuple(ratings)
    if len(values) < min_count:
        return "UNTESTED"
    if len({rating.rater_pseudonym for rating in values}) < min_count:
        return "NEEDS_REVIEW"
    scores = [rating.score for rating in values]
    if all(score == 2 for score in scores):
        return "GREEN"
    if any(score == 0 for score in scores):
        return "RED"
    return "YELLOW"


def load_benchmark(path: str | Path) -> BenchmarkManifest:
    return BenchmarkManifest.from_yaml(path)


load_manifest = load_benchmark
