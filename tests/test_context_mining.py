from pathlib import Path

import pytest

from khalkha_frontend.context_mining import (
    mine_word,
    read_frequency_list,
)
from khalkha_frontend.tokenizer_audit import collect_frequency


def test_frequency_reader_validates_and_orders(tmp_path: Path):
    path = tmp_path / "words.csv"
    path.write_text("word,frequency\nлала,0.1\nхэл,0.8\n", encoding="utf-8")
    rows = read_frequency_list(path)
    assert [row.word for row in rows] == ["хэл", "лала"]


def test_frequency_collector_honors_zero_and_rejects_negative(tmp_path: Path):
    path = tmp_path / "words.csv"
    path.write_text("word,frequency\nхэл,0.8\n", encoding="utf-8")
    assert collect_frequency(path, 0) == ()
    with pytest.raises(ValueError, match="non-negative"):
        collect_frequency(path, -1)


@pytest.mark.parametrize("value", ["-1", "nan", "inf", "nope"])
def test_frequency_reader_rejects_invalid_numbers(tmp_path: Path, value: str):
    path = tmp_path / "words.csv"
    path.write_text(f"word,frequency\nхэл,{value}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="frequency"):
        read_frequency_list(path)


def test_context_labels_cover_multiple_occurrences_and_special_letters():
    candidates = mine_word("хэлүүл", source="frequency", groups=("L", "H", "PALATALIZATION"))
    assert {item.occurrence_index for item in candidates if item.target_grapheme == "л"} == {2, 5}
    assert any(item.group == "H" and item.pattern == "CV" for item in candidates)
    soft = mine_word("нь", source="frequency", groups=("PALATALIZATION",))
    assert any(item.pattern == "soft_sign" for item in soft)


def test_context_labels_only_match_literal_neighbors():
    vcv = mine_word("ала", source="frequency", groups=("L",))
    assert any(item.pattern == "VCV" for item in vcv)
    assert not any(item.pattern == "preconsonantal" for item in vcv)
    final = mine_word("мал", source="frequency", groups=("L",))
    assert any(item.pattern == "final" for item in final)
    assert not any(item.pattern == "Ci_candidate" for item in final)
    ci = mine_word("сили", source="frequency", groups=("PALATALIZATION",))
    assert any(item.target_grapheme == "л" and item.pattern == "Ci_candidate" for item in ci)


def test_ng_is_only_the_literal_adjacency():
    for word, position in (("нг", "only"), ("нгар", "initial"), ("анг", "final"), ("ангар", "medial")):
        candidates = mine_word(word, source="frequency", groups=("NG",))
        assert [(item.target_grapheme, item.pattern, item.position) for item in candidates] == [("нг", "ng", position)]


def test_candidate_has_no_phonetic_value():
    candidate = mine_word("хэл", source="frequency", groups=("L",))[0]
    assert "not a phone prediction" in candidate.note
    assert not hasattr(candidate, "expected_phone")
