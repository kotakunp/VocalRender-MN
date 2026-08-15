# fmt: off

import pytest

from khalkha_frontend import (
    EvidenceRef,
    FrontendResult,
    NormalizedText,
    PronunciationUnit,
    ResolutionStatus,
    TextIssue,
    TextIssueKind,
)

EVIDENCE = EvidenceRef(
    "bench-1", "benchmark", "benchmarks/MN-PHON-250", note="manual review"
)


def test_text_issue_rejects_invalid_spans():
    with pytest.raises(ValueError):
        TextIssue(TextIssueKind.NUMBER, "1", 2, 1, "invalid")


def test_normalized_and_frontend_tuples_are_immutable():
    normalized = NormalizedText(
        "а", "а", [TextIssue(TextIssueKind.NUMBER, "1", 0, 1, "issue")]
    )
    result = FrontendResult(normalized, ["а"], [], normalized.issues)

    assert isinstance(normalized.issues, tuple)
    assert isinstance(result.lyric_units, tuple)
    with pytest.raises(AttributeError):
        result.lyric_units.append("б")


def test_resolved_phone_values_require_evidence():
    with pytest.raises(ValueError):
        PronunciationUnit(
            "сайн", phonemic_symbols=("x",), status=ResolutionStatus.RESOLVED
        )


def test_research_required_can_have_unresolved_phone_fields():
    unit = PronunciationUnit("сайн", status=ResolutionStatus.RESEARCH_REQUIRED)

    assert unit.phonemic_symbols is None
    assert unit.surface_phones is None


def test_overridden_value_requires_provenance_note():
    with pytest.raises(ValueError):
        PronunciationUnit(
            "сайн",
            status=ResolutionStatus.OVERRIDDEN,
            manual_override="manual",
            evidence_refs=(EvidenceRef("manual-1", "note", "notes.md"),),
        )


def test_evidence_allows_resolved_phone_values():
    unit = PronunciationUnit(
        "сайн",
        phonemic_symbols=("x",),
        status=ResolutionStatus.RESOLVED,
        evidence_refs=(EVIDENCE,),
    )

    assert unit.evidence_refs == (EVIDENCE,)

# fmt: on
