import subprocess
import sys

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

EVIDENCE = EvidenceRef("bench-1", "benchmark", "benchmarks/MN-PHON-250", note="manual review")


def test_package_import_does_not_load_vocalrender_or_torch():
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, khalkha_frontend; "
            "assert 'torch' not in sys.modules; assert 'vocalrender' not in sys.modules",
        ],
        check=True,
    )


@pytest.mark.parametrize("field", ("stable_id", "source_kind", "citation_or_path"))
def test_evidence_ref_requires_nonempty_identity_fields(field):
    values = {
        "stable_id": "stable",
        "source_kind": "benchmark",
        "citation_or_path": "benchmarks/MN-PHON-250",
    }
    values[field] = "  "

    with pytest.raises(ValueError):
        EvidenceRef(**values)


def test_evidence_ref_benchmark_aliases_preserve_canonical_provenance():
    reference = EvidenceRef(
        id="native-review-1",
        source="benchmarks/MN-PHON-250/evaluations.yaml",
        kind="native_speaker_validation",
        notes="reviewed item",
    )

    assert reference.stable_id == reference.id == "native-review-1"
    assert reference.source_kind == reference.kind == "native_speaker_validation"
    assert reference.citation_or_path == reference.source
    assert reference.note == reference.notes == "reviewed item"


def test_text_issue_rejects_invalid_spans():
    with pytest.raises(ValueError):
        TextIssue(TextIssueKind.NUMBER, "1", 2, 1, "invalid")


def test_normalized_and_frontend_tuples_are_immutable():
    normalized = NormalizedText("а", "а", [TextIssue(TextIssueKind.NUMBER, "1", 0, 1, "issue")])
    result = FrontendResult(normalized, ["а"], [], normalized.issues)

    assert isinstance(normalized.issues, tuple)
    assert isinstance(result.lyric_units, tuple)
    with pytest.raises(AttributeError):
        result.lyric_units.append("б")


def test_resolved_phone_values_require_evidence():
    with pytest.raises(ValueError):
        PronunciationUnit("сайн", phonemic_symbols=("x",), status=ResolutionStatus.RESOLVED)

    with pytest.raises(ValueError):
        PronunciationUnit("сайн", status=ResolutionStatus.RESOLVED)


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
