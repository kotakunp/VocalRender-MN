# fmt: off

"""Neutral, uncertainty-preserving values shared by frontend stages."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

_RESOLVED_ERROR = (
    "resolved phone values require at least one evidence reference"
)
_OVERRIDE_EMPTY_ERROR = (
    "overridden pronunciation requires a nonempty manual override"
)
_OVERRIDE_NOTE_ERROR = (
    "overridden pronunciation requires an evidence/provenance note"
)


class ResolutionStatus(str, Enum):
    """How confidently a frontend value has been resolved."""

    RESOLVED = "resolved"
    RESEARCH_REQUIRED = "research_required"
    OVERRIDDEN = "overridden"
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
            raise ValueError(
                "text issue spans must be nonnegative and ordered",
            )


@dataclass(frozen=True)
class NormalizedText:
    """Original and safely normalized text plus unresolved issues."""

    original: str
    normalized: str
    issues: Tuple[TextIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))


@dataclass(frozen=True)
class EvidenceRef:
    """A stable provenance reference for a resolved pronunciation value."""

    stable_id: str
    source_kind: str
    citation_or_path: str
    item_id: Optional[str] = None
    note: str = ""


@dataclass(frozen=True)
class PronunciationUnit:
    """Orthography and optional evidence-gated pronunciation information."""

    orthographic_text: str
    phonemic_symbols: Optional[Tuple[str, ...]] = None
    surface_phones: Optional[Tuple[str, ...]] = None
    status: ResolutionStatus = ResolutionStatus.RESEARCH_REQUIRED
    evidence_refs: Tuple[EvidenceRef, ...] = ()
    manual_override: Optional[str] = None

    def __post_init__(self) -> None:
        evidence = tuple(self.evidence_refs)
        phonemes = (
            tuple(self.phonemic_symbols) if self.phonemic_symbols else None
        )
        phones = tuple(self.surface_phones) if self.surface_phones else None
        object.__setattr__(self, "evidence_refs", evidence)
        object.__setattr__(self, "phonemic_symbols", phonemes)
        object.__setattr__(self, "surface_phones", phones)
        if self.status is ResolutionStatus.RESOLVED:
            if (phonemes or phones) and not evidence:
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
    lyric_units: Tuple[str, ...] = ()
    pronunciation_units: Tuple[PronunciationUnit, ...] = ()
    issues: Tuple[TextIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "lyric_units", tuple(self.lyric_units))
        pronunciation_units = tuple(self.pronunciation_units)
        object.__setattr__(self, "pronunciation_units", pronunciation_units)
        object.__setattr__(self, "issues", tuple(self.issues))

# fmt: on
