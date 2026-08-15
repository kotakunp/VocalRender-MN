import pytest

from khalkha_frontend.syllabify import ConservativeSyllabifier
from khalkha_frontend.types import ResolutionStatus

EVIDENCE = [{"id": "synthetic-1", "source": "tests/fixtures/synthetic", "kind": "synthetic"}]


def test_empty_and_unknown_input_are_explicit() -> None:
    syllabifier = ConservativeSyllabifier()
    assert syllabifier.syllabify("") == ()
    result = syllabifier.syllabify("чамдаа")
    assert len(result) == 1
    assert result[0].text == "чамдаа"
    assert result[0].status is ResolutionStatus.RESEARCH_REQUIRED


def test_synthetic_override_preserves_spans() -> None:
    syllabifier = ConservativeSyllabifier({"abc": {"segments": ["a", "bc"], "evidence": EVIDENCE}})
    result = syllabifier.syllabify("abc")
    assert [(candidate.text, candidate.start, candidate.end) for candidate in result] == [("a", 0, 1), ("bc", 1, 3)]


def test_alternatives_are_not_selected_by_vowel_heuristic() -> None:
    syllabifier = ConservativeSyllabifier(
        {
            "abc": [
                {"segments": ["a", "bc"], "evidence": EVIDENCE},
                {"segments": ["ab", "c"], "evidence": EVIDENCE},
            ]
        }
    )
    alternatives = syllabifier.alternatives("abc")
    assert len(alternatives) == 2
    assert [candidate.text for candidate in alternatives[1]] == ["ab", "c"]
    unresolved = syllabifier.syllabify("abc")
    assert len(unresolved) == 1
    assert unresolved[0].status is ResolutionStatus.RESEARCH_REQUIRED
    assert unresolved[0].text == "abc"
    assert unresolved[0].alternatives


def test_unreviewed_override_is_rejected() -> None:
    with pytest.raises(ValueError, match="require evidence"):
        ConservativeSyllabifier({"abc": ["a", "bc"]}).syllabify("abc")


def test_missing_evidence_source_is_rejected() -> None:
    with pytest.raises(ValueError, match="id and source"):
        ConservativeSyllabifier(
            {"abc": {"segments": ["a", "bc"], "evidence": [{"id": "e", "source": None}]}}
        ).syllabify("abc")
