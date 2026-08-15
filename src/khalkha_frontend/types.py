"""Shared, immutable, uncertainty-preserving frontend value types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

_RESOLVED_ERROR = "resolved phone values require at least one evidence reference"
_OVERRIDE_EMPTY_ERROR = "overridden pronunciation requires a nonempty manual override"
_OVERRIDE_NOTE_ERROR = "overridden pronunciation requires an evidence/provenance note"


class ResolutionStatus(str, Enum):
    """How confidently a frontend value has been resolved."""

    RESOLVED = "resolved"
    RESEARCH_REQUIRED = "research_required"
    OVERRIDDEN = "overridden"
    UNRESOLVED = "unresolved"
    UNSUPPORTED = "unsupported"


class TextIssueKind(str, Enum):
    """Typed conditions that require downstream review."""

    NUMBER = "number"
    ABBREVIATION = "abbreviation"
    FOREIGN_SCRIPT = "foreign_script"
    UNSUPPORTED_CHARACTER = "unsupported_character"


@dataclass(frozen=True)
class TextIssue:
    """An issue with a span in normalized text."""

    kind: TextIssueKind
    original: str
    start: int
    end: int
    message: str

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError("text issue spans must be nonnegative and ordered")


@dataclass(frozen=True)
class NormalizedText:
    """Original and safely normalized text plus unresolved issues."""

    original: str
    normalized: str
    issues: tuple[TextIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))


@dataclass(frozen=True, init=False)
class EvidenceRef:
    """A stable provenance reference supporting a linguistic decision.

    The canonical fields come from the frontend contract. ``id``, ``source``,
    ``kind``, and ``notes`` remain read-only aliases for the benchmark schema.
    """

    stable_id: str
    source_kind: str
    citation_or_path: str
    item_id: str | None
    note: str
    reviewer: str | None
    status: str
    date: str | None

    def __init__(
        self,
        stable_id: str | None = None,
        source_kind: str | None = None,
        citation_or_path: str | None = None,
        item_id: str | None = None,
        note: str = "",
        *,
        id: str | None = None,
        source: str | None = None,
        kind: str | None = None,
        reviewer: str | None = None,
        status: str = "unreviewed",
        date: str | None = None,
        notes: str | None = None,
    ) -> None:
        if id is not None:
            if stable_id is not None and stable_id != id:
                raise ValueError("conflicting evidence stable_id/id values")
            stable_id = id
        if source is not None:
            if citation_or_path is not None and citation_or_path != source:
                raise ValueError("conflicting evidence citation_or_path/source values")
            citation_or_path = source
        # Two positional arguments were used by the benchmark scaffold as
        # (id, source). Preserve that compatibility without weakening the
        # canonical three-field provenance contract.
        if citation_or_path is None and source_kind is not None:
            citation_or_path = source_kind
            source_kind = kind or "unspecified"
        elif kind is not None and str(kind).strip():
            if source_kind is not None and source_kind != kind:
                raise ValueError("conflicting evidence source_kind/kind values")
            source_kind = str(kind)
        if source_kind is None:
            source_kind = "unspecified"
        if notes is not None:
            if note and note != notes:
                raise ValueError("conflicting evidence note/notes values")
            note = notes
        values = {
            "stable_id": stable_id,
            "source_kind": source_kind,
            "citation_or_path": citation_or_path,
        }
        for field_name, value in values.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a nonempty string")
        object.__setattr__(self, "stable_id", stable_id)
        object.__setattr__(self, "source_kind", source_kind)
        object.__setattr__(self, "citation_or_path", citation_or_path)
        object.__setattr__(self, "item_id", item_id)
        object.__setattr__(self, "note", note)
        object.__setattr__(self, "reviewer", reviewer)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "date", date)

    @property
    def id(self) -> str:
        return self.stable_id

    @property
    def source(self) -> str:
        return self.citation_or_path

    @property
    def kind(self) -> str:
        return self.source_kind

    @property
    def notes(self) -> str:
        return self.note


def _evidence(value: Sequence[EvidenceRef | Mapping[str, Any]] | None) -> tuple[EvidenceRef, ...]:
    result: list[EvidenceRef] = []
    for entry in value or ():
        if isinstance(entry, EvidenceRef):
            result.append(entry)
            continue
        if not isinstance(entry, Mapping):
            raise ValueError("evidence entries must be mappings")
        stable_id = entry.get("stable_id") or entry.get("id")
        citation = (
            entry.get("citation_or_path") or entry.get("source") or entry.get("source_url") or entry.get("local_path")
        )
        source_kind = entry.get("source_kind") or entry.get("kind") or "unspecified"
        result.append(
            EvidenceRef(
                stable_id=str(stable_id) if stable_id is not None else None,
                source_kind=str(source_kind),
                citation_or_path=str(citation) if citation is not None else None,
                item_id=entry.get("item_id"),
                note=str(entry.get("note", entry.get("notes", ""))),
                reviewer=entry.get("reviewer"),
                status=str(entry.get("status", "unreviewed")),
                date=entry.get("date"),
            )
        )
    return tuple(result)


def _symbols(value: Sequence[str] | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes)):
        raise ValueError("symbols must be a sequence of strings, not one string")
    return tuple(value)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class PronunciationUnit:
    """Orthography and optional evidence-gated pronunciation information."""

    orthographic_text: str
    phonemic_symbols: tuple[str, ...] | None = None
    surface_phones: tuple[str, ...] | None = None
    status: ResolutionStatus = ResolutionStatus.RESEARCH_REQUIRED
    evidence_refs: tuple[EvidenceRef, ...] = ()
    manual_override: str | None = None

    def __post_init__(self) -> None:
        evidence = _evidence(self.evidence_refs)
        phonemes = _symbols(self.phonemic_symbols)
        phones = _symbols(self.surface_phones)
        object.__setattr__(self, "evidence_refs", evidence)
        object.__setattr__(self, "phonemic_symbols", phonemes)
        object.__setattr__(self, "surface_phones", phones)
        if self.status is ResolutionStatus.RESOLVED and not evidence:
            raise ValueError(_RESOLVED_ERROR)
        if self.status is ResolutionStatus.OVERRIDDEN:
            if not self.manual_override or not self.manual_override.strip():
                raise ValueError(_OVERRIDE_EMPTY_ERROR)
            if not evidence or not any(ref.note.strip() for ref in evidence):
                raise ValueError(_OVERRIDE_NOTE_ERROR)


@dataclass(frozen=True)
class FrontendResult:
    """Neutral frontend output; unresolved units remain representable."""

    normalized_text: NormalizedText
    lyric_units: tuple[str, ...] = ()
    pronunciation_units: tuple[PronunciationUnit, ...] = ()
    issues: tuple[TextIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "lyric_units", tuple(self.lyric_units))
        object.__setattr__(self, "pronunciation_units", tuple(self.pronunciation_units))
        object.__setattr__(self, "issues", tuple(self.issues))


@dataclass(frozen=True)
class SyllableCandidate:
    text: str
    start: int
    end: int
    status: ResolutionStatus = ResolutionStatus.RESEARCH_REQUIRED
    evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    alternatives: tuple["SyllableCandidate", ...] = field(default_factory=tuple)
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("syllable candidate must preserve non-empty text")
        if self.start < 0 or self.end < self.start:
            raise ValueError("syllable span must be non-negative and ordered")
        object.__setattr__(self, "evidence", _evidence(self.evidence))
        object.__setattr__(self, "alternatives", tuple(self.alternatives))
        if self.status in (ResolutionStatus.RESOLVED, ResolutionStatus.OVERRIDDEN) and not self.evidence:
            raise ValueError("resolved or overridden syllables require evidence")


@dataclass(frozen=True)
class PhonemeCandidate:
    symbols: tuple[str, ...] | None
    status: ResolutionStatus = ResolutionStatus.RESEARCH_REQUIRED
    evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    source_text: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        normalized = _symbols(self.symbols)
        if normalized is not None and any(not symbol for symbol in normalized):
            raise ValueError("phoneme symbols may not contain empty strings")
        if self.status in (ResolutionStatus.RESOLVED, ResolutionStatus.OVERRIDDEN) and not normalized:
            raise ValueError("resolved or overridden phonemes require non-empty symbols")
        object.__setattr__(self, "symbols", normalized)
        object.__setattr__(self, "evidence", _evidence(self.evidence))
        if self.status in (ResolutionStatus.RESOLVED, ResolutionStatus.OVERRIDDEN) and not self.evidence:
            raise ValueError("resolved or overridden phonemes require evidence")
        if self.status == ResolutionStatus.RESEARCH_REQUIRED and normalized is not None:
            raise ValueError("research-required phonemes must keep symbols unset")


@dataclass(frozen=True)
class PhoneCandidate:
    symbols: tuple[str, ...] | None
    status: ResolutionStatus = ResolutionStatus.RESEARCH_REQUIRED
    evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    phonological_environment: Mapping[str, Any] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        normalized = _symbols(self.symbols)
        if normalized is not None and any(not symbol for symbol in normalized):
            raise ValueError("phone symbols may not contain empty strings")
        if self.status in (ResolutionStatus.RESOLVED, ResolutionStatus.OVERRIDDEN) and not normalized:
            raise ValueError("resolved or overridden phones require non-empty symbols")
        object.__setattr__(self, "symbols", normalized)
        object.__setattr__(self, "evidence", _evidence(self.evidence))
        object.__setattr__(self, "phonological_environment", _freeze(self.phonological_environment))
        if self.status in (ResolutionStatus.RESOLVED, ResolutionStatus.OVERRIDDEN) and not self.evidence:
            raise ValueError("resolved or overridden phones require evidence")
        if self.status == ResolutionStatus.RESEARCH_REQUIRED and normalized is not None:
            raise ValueError("research-required phones must keep symbols unset")


@dataclass(frozen=True)
class PronunciationOverride:
    id: str
    orthography: str | None = None
    item_scope: str | None = None
    symbols: tuple[str, ...] = field(default_factory=tuple)
    level: str = "phonemic"
    evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    provenance: str = ""
    review_status: str = "unreviewed"
    expires: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip() or not (self.orthography or self.item_scope):
            raise ValueError("override requires an id and orthography or item scope")
        if self.level not in ("phonemic", "surface"):
            raise ValueError("override level must be phonemic or surface")
        symbols = _symbols(self.symbols)
        if not symbols or any(not symbol for symbol in symbols):
            raise ValueError("override symbols must be non-empty")
        object.__setattr__(self, "symbols", symbols)
        object.__setattr__(self, "evidence", _evidence(self.evidence))
        if not self.evidence:
            raise ValueError("pronunciation overrides require an evidence reference")
