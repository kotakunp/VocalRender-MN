import pytest

from khalkha_frontend.allophones import AllophoneResolver, AllophoneRule, PhonologicalEnvironment
from khalkha_frontend.types import EvidenceRef, PhonemeCandidate, ResolutionStatus

EVIDENCE = (EvidenceRef("synthetic-rule", "tests/fixtures/synthetic"),)


def test_empty_production_rules_do_not_fabricate_surface_phones() -> None:
    candidate = PhonemeCandidate(("P",), ResolutionStatus.RESOLVED, EVIDENCE, "abc")
    result = AllophoneResolver().resolve(candidate)
    assert result.symbols == ("P",)
    assert result.status is ResolutionStatus.UNRESOLVED


def test_synthetic_rule_priority_and_environment() -> None:
    rules = [
        AllophoneRule("low", 1, "P", "low", {"position": "final"}, EVIDENCE, ResolutionStatus.RESOLVED),
        AllophoneRule("high", 2, "P", "high", {"position": "final"}, EVIDENCE, ResolutionStatus.RESOLVED),
    ]
    result = AllophoneResolver(rules).resolve(
        PhonemeCandidate(("P",), ResolutionStatus.RESOLVED, EVIDENCE, "abc"),
        PhonologicalEnvironment(position="final"),
    )
    assert result.symbols == ("high",)


def test_conflicting_same_priority_rules_are_rejected() -> None:
    with pytest.raises(ValueError, match="conflicting"):
        AllophoneResolver(
            [
                AllophoneRule("one", 1, "P", "A", {}, EVIDENCE, ResolutionStatus.RESOLVED),
                AllophoneRule("two", 1, "P", "B", {}, EVIDENCE, ResolutionStatus.RESOLVED),
            ]
        )


def test_missing_evidence_source_and_environment_are_rejected_or_immutable() -> None:
    with pytest.raises(ValueError, match="id and source"):
        AllophoneRule.from_mapping(
            {
                "id": "bad",
                "priority": 1,
                "input_phone_id": "P",
                "output_phone_id": "Q",
                "status": "resolved",
                "evidence": [{"id": "e", "source": None}],
            },
            0,
        )
    candidate = AllophoneResolver().resolve(
        PhonemeCandidate(("P",), ResolutionStatus.RESOLVED, EVIDENCE, "abc"),
        PhonologicalEnvironment(position="final"),
    )
    with pytest.raises(TypeError):
        candidate.phonological_environment["position"] = "initial"


def test_active_rule_status_and_direct_fields_are_gated() -> None:
    with pytest.raises(ValueError, match="resolved or overridden"):
        AllophoneRule("unresolved", 1, "P", "Q", {}, EVIDENCE, ResolutionStatus.UNRESOLVED)
    with pytest.raises(ValueError, match="non-empty"):
        AllophoneRule("", 1, "P", "Q", {}, EVIDENCE, ResolutionStatus.RESOLVED)
