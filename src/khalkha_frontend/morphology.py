"""Read-only access to the local UniMorph Khalkha resources.

The observed files have deliberately different, tab-separated schemas:

* ``khk``: ``lemma, surface, features`` (30,143 rows in the inspected copy).
* ``khk.segmentations``: ``lemma, surface, features, segmentation`` (30,129).
* ``khk.derivations``: six raw columns, observed as ``lemma, derived, source
  category, target category, affix, relation`` (1,629).  The derivation
  columns are exposed losslessly because this module does not infer semantics
  beyond the file's literal fields.

This module contains morphology facts only.  It does not turn spelling into
pronunciation or provide a phonetic dictionary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import unicodedata


class MorphologyFormatError(ValueError):
    """Raised when a UniMorph row does not have its documented shape."""


def _normalize_word(word: str) -> str:
    """Use the foundation normalizer when installed, with a safe fallback."""
    if not isinstance(word, str):
        raise TypeError("word must be a string")
    try:
        from .normalize import normalize_text

        return normalize_text(word).normalized
    except ImportError:
        return " ".join(unicodedata.normalize("NFC", word).split()).lower()


@dataclass(frozen=True)
class MorphAnalysis:
    lemma: str
    surface: str
    features: tuple[str, ...]
    source_line: int


@dataclass(frozen=True)
class Segmentation:
    lemma: str
    surface: str
    features: tuple[str, ...]
    morphemes: tuple[str, ...]
    source_line: int


@dataclass(frozen=True)
class DerivationRow:
    """Lossless six-field derivation row; fields retain source spelling."""

    fields: tuple[str, ...]
    source_line: int


@dataclass(frozen=True)
class MorphologyLookup:
    analyses: tuple[MorphAnalysis, ...] = ()
    segmentations: tuple[Segmentation, ...] = ()
    known: bool = False


class UniMorphKhalkha:
    """Lazy, read-only parser for one ``resources/unimorph_khk`` directory."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self._analyses: dict[str, list[MorphAnalysis]] | None = None
        self._segmentations: dict[str, list[Segmentation]] | None = None

    def _file(self, name: str) -> Path:
        path = self.directory / name
        if not path.is_file():
            raise FileNotFoundError(
                f"UniMorph Khalkha resource is missing: {path}. " "Pass the semantic resources/unimorph_khk directory."
            )
        return path

    @staticmethod
    def _fields(path: Path, line_number: int, line: str, expected: int) -> list[str]:
        fields = line.rstrip("\r\n").split("\t")
        if len(fields) != expected or any(field == "" for field in fields):
            raise MorphologyFormatError(
                f"{path}:{line_number}: expected {expected} non-empty tab-separated fields, " f"got {len(fields)}"
            )
        return fields

    @staticmethod
    def _bundle(raw: str) -> tuple[str, ...]:
        return tuple(part for part in raw.split(";") if part)

    def _load_analyses(self) -> dict[str, list[MorphAnalysis]]:
        index: dict[str, list[MorphAnalysis]] = {}
        path = self._file("khk")
        with path.open("r", encoding="utf-8", newline="") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                lemma, surface, features = self._fields(path, line_number, line, 3)
                record = MorphAnalysis(lemma, surface, self._bundle(features), line_number)
                index.setdefault(_normalize_word(surface), []).append(record)
        return index

    def _load_segmentations(self) -> dict[str, list[Segmentation]]:
        index: dict[str, list[Segmentation]] = {}
        path = self._file("khk.segmentations")
        with path.open("r", encoding="utf-8", newline="") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                lemma, surface, features, segmentation = self._fields(path, line_number, line, 4)
                morphemes = tuple(segmentation.split("|"))
                if not morphemes or any(not part for part in morphemes):
                    raise MorphologyFormatError(f"{path}:{line_number}: invalid empty morpheme")
                record = Segmentation(lemma, surface, self._bundle(features), morphemes, line_number)
                index.setdefault(_normalize_word(surface), []).append(record)
        return index

    def lookup(self, word: str) -> MorphologyLookup:
        key = _normalize_word(word)
        if self._analyses is None:
            self._analyses = self._load_analyses()
        if self._segmentations is None:
            self._segmentations = self._load_segmentations()
        analyses = tuple(self._analyses.get(key, ()))
        segmentations = tuple(self._segmentations.get(key, ()))
        return MorphologyLookup(analyses, segmentations, bool(analyses or segmentations))

    def analyses(self, word: str) -> tuple[MorphAnalysis, ...]:
        return self.lookup(word).analyses

    def segmentations(self, word: str) -> tuple[Segmentation, ...]:
        return self.lookup(word).segmentations

    def iter_analyses(self, limit: int | None = None) -> Iterator[MorphAnalysis]:
        """Stream inflection rows in source order with an optional cap."""
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative or None")
        if limit == 0:
            return
        path = self._file("khk")
        yielded = 0
        with path.open("r", encoding="utf-8", newline="") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                lemma, surface, features = self._fields(path, line_number, line, 3)
                yield MorphAnalysis(lemma, surface, self._bundle(features), line_number)
                yielded += 1
                if limit is not None and yielded >= limit:
                    return

    def iter_segmentations(self, limit: int | None = None) -> Iterator[Segmentation]:
        """Stream segmentation rows in source order with an optional cap."""
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative or None")
        if limit == 0:
            return
        path = self._file("khk.segmentations")
        yielded = 0
        with path.open("r", encoding="utf-8", newline="") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                lemma, surface, features, segmentation = self._fields(path, line_number, line, 4)
                morphemes = tuple(segmentation.split("|"))
                if any(not part for part in morphemes):
                    raise MorphologyFormatError(f"{path}:{line_number}: empty morpheme")
                yield Segmentation(lemma, surface, self._bundle(features), morphemes, line_number)
                yielded += 1
                if limit is not None and yielded >= limit:
                    return

    def iter_derivations(self, limit: int | None = None) -> Iterator[DerivationRow]:
        """Yield raw derivation rows without assigning undocumented semantics."""
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative or None")
        if limit == 0:
            return
        path = self._file("khk.derivations")
        yielded = 0
        with path.open("r", encoding="utf-8", newline="") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                fields = tuple(line.rstrip("\r\n").split("\t"))
                if len(fields) != 6 or any(field == "" for field in fields):
                    raise MorphologyFormatError(
                        f"{path}:{line_number}: expected six non-empty tab-separated fields, got {len(fields)}"
                    )
                yield DerivationRow(fields, line_number)
                yielded += 1
                if limit is not None and yielded >= limit:
                    return


def analyze_word(word: str, resource: UniMorphKhalkha) -> MorphologyLookup:
    """Return morphology for ``word`` using an explicitly injected resource."""
    return resource.lookup(word)


def segment_morphemes(word: str, resource: UniMorphKhalkha) -> tuple[Segmentation, ...]:
    """Return the source-provided segmentation records for ``word``."""
    return resource.segmentations(word)
