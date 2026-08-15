"""Conservative Unicode normalization for Standard Khalkha text.

Only reversible Unicode and whitespace operations are performed. Digits,
abbreviations, foreign scripts, and unsupported controls remain in the text
and are reported as typed issues rather than being assigned pronunciations.
"""

import re
import unicodedata

from .types import NormalizedText, TextIssue, TextIssueKind

_CYRILLIC = re.compile(r"[\u0400-\u04ff]")
_LATIN_RUN = re.compile(r"[A-Za-z]+")
_DIGIT_RUN = re.compile(r"\d+")
_ABBREVIATION = re.compile(r"(?<!\w)(?:[А-ЯЁӨҮ]){2,}(?!\w)|(?<!\w)(?:[А-ЯЁӨҮа-яёөү][.]){2,}")


def normalize_text(text: str, *, lowercase: bool = True) -> NormalizedText:
    """Return NFC, whitespace-normalized text without pronunciation guesses."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    normalized = unicodedata.normalize("NFC", text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    issue_text = normalized
    if lowercase:
        normalized = normalized.lower()

    issues = []
    for match in _DIGIT_RUN.finditer(normalized):
        issues.append(
            TextIssue(
                TextIssueKind.NUMBER,
                match.group(),
                match.start(),
                match.end(),
                "number expansion is unresolved",
            )
        )
    for match in _ABBREVIATION.finditer(issue_text):
        issues.append(
            TextIssue(
                TextIssueKind.ABBREVIATION,
                match.group(),
                match.start(),
                match.end(),
                "abbreviation expansion is unresolved",
            )
        )
    for match in _LATIN_RUN.finditer(normalized):
        issues.append(
            TextIssue(
                TextIssueKind.FOREIGN_SCRIPT,
                match.group(),
                match.start(),
                match.end(),
                "foreign-script pronunciation is unresolved",
            )
        )
    for index, character in enumerate(normalized):
        category = unicodedata.category(character)
        if category.startswith("C") and not character.isspace():
            issues.append(
                TextIssue(
                    TextIssueKind.UNSUPPORTED_CHARACTER,
                    character,
                    index,
                    index + 1,
                    "control or unsupported character is preserved",
                )
            )
    return NormalizedText(text, normalized, tuple(issues))
