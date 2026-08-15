# fmt: off

import unicodedata

import pytest

from khalkha_frontend import TextIssueKind, normalize_text


def test_nfc_equivalence_and_whitespace_are_normalized():
    decomposed = "и\u0306\tСайн\nүг"

    result = normalize_text(decomposed)

    assert result.normalized == "й сайн үг"
    assert unicodedata.is_normalized("NFC", result.normalized)


def test_special_cyrillic_letters_are_preserved():
    text = "Ө ө Ү ү Ё ё Ь ь Ъ ъ"

    assert normalize_text(text, lowercase=False).normalized == text


def test_punctuation_and_digits_are_preserved_and_digits_are_reported():
    result = normalize_text("Сайн, 2026!")

    assert result.normalized == "сайн, 2026!"
    assert [issue.kind for issue in result.issues] == [TextIssueKind.NUMBER]


def test_latin_text_is_preserved_and_reported_as_foreign_script():
    result = normalize_text("hello")

    assert result.normalized == "hello"
    assert result.issues[0].kind is TextIssueKind.FOREIGN_SCRIPT


def test_abbreviation_and_control_are_typed_without_dropping_content():
    result = normalize_text("НҮБ\x00 т.н.")

    assert result.normalized == "нүб\x00 т.н."
    assert TextIssueKind.ABBREVIATION in {
        issue.kind for issue in result.issues
    }
    assert TextIssueKind.UNSUPPORTED_CHARACTER in {
        issue.kind for issue in result.issues
    }


def test_empty_input_and_idempotence():
    result = normalize_text("  ")

    assert result.normalized == ""
    assert normalize_text(result.normalized).normalized == result.normalized


def test_non_string_input_is_rejected():
    with pytest.raises(TypeError):
        normalize_text(None)

# fmt: on
