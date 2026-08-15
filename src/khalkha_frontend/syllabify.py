"""Conservative, evidence-gated syllabification interfaces."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from .types import EvidenceRef, ResolutionStatus, SyllableCandidate


class Syllabifier(Protocol):
    def syllabify(self, text: str) -> tuple[SyllableCandidate, ...]: ...


def _evidence(raw: Any) -> tuple[EvidenceRef, ...]:
    result: list[EvidenceRef] = []
    for entry in raw or ():
        if isinstance(entry, EvidenceRef):
            result.append(entry)
        else:
            if not isinstance(entry, Mapping):
                raise ValueError("evidence entries must be mappings")
            source = entry.get("source") or entry.get("source_url") or entry.get("local_path")
            if (
                not isinstance(entry.get("id"), str)
                or not entry["id"].strip()
                or not isinstance(source, str)
                or not source.strip()
            ):
                raise ValueError("evidence entries require non-empty id and source")
            result.append(
                EvidenceRef(
                    id=str(entry["id"]),
                    source=source,
                    kind=str(entry.get("kind", "")),
                    reviewer=entry.get("reviewer"),
                    status=str(entry.get("status", "unreviewed")),
                    date=entry.get("date"),
                    notes=str(entry.get("notes", "")),
                )
            )
    return tuple(result)


class ConservativeSyllabifier:
    """Use only explicitly supplied segmentations; otherwise preserve the word."""

    def __init__(self, overrides: Mapping[str, Any] | None = None) -> None:
        self._overrides = dict(overrides or {})

    def syllabify(self, text: str) -> tuple[SyllableCandidate, ...]:
        normalized = unicodedata.normalize("NFC", text)
        if not normalized:
            return ()
        if normalized not in self._overrides:
            return (
                SyllableCandidate(
                    text=normalized,
                    start=0,
                    end=len(normalized),
                    status=ResolutionStatus.RESEARCH_REQUIRED,
                    notes="No evidence-backed segmentation is registered; whole token preserved.",
                ),
            )
        raw = self._overrides[normalized]
        alternatives = raw if isinstance(raw, list) and raw and isinstance(raw[0], Mapping) else [raw]
        if len(alternatives) > 1:
            flattened = tuple(
                candidate
                for alternative in alternatives
                for candidate in self._alternative_candidates(normalized, alternative)
            )
            return (
                SyllableCandidate(
                    text=normalized,
                    start=0,
                    end=len(normalized),
                    status=ResolutionStatus.RESEARCH_REQUIRED,
                    alternatives=flattened,
                    notes="Multiple evidence-backed alternatives are available; explicit selection is required.",
                ),
            )
        candidates: list[SyllableCandidate] = []
        for alternative in alternatives:
            if isinstance(alternative, Mapping):
                segments = alternative.get("segments")
                evidence = _evidence(alternative.get("evidence"))
                note = str(alternative.get("notes", ""))
            else:
                segments = alternative
                evidence = ()
                note = ""
            if not isinstance(segments, Sequence) or isinstance(segments, (str, bytes)):
                raise ValueError(f"override for {normalized!r} must provide ordered segments")
            joined = "".join(str(segment) for segment in segments)
            if joined != normalized:
                raise ValueError(f"override for {normalized!r} does not cover exact normalized text")
            candidates.extend(self._make_candidates(segments, evidence, note))
        if not candidates:
            return (
                SyllableCandidate(
                    text=normalized,
                    start=0,
                    end=len(normalized),
                    status=ResolutionStatus.RESEARCH_REQUIRED,
                    notes="Registered override did not yield a segmentation.",
                ),
            )
        return tuple(candidates)

    segment = syllabify

    def alternatives(self, text: str) -> tuple[tuple[SyllableCandidate, ...], ...]:
        """Return all evidence-tagged alternatives without selecting among them."""

        normalized = unicodedata.normalize("NFC", text)
        raw = self._overrides.get(normalized)
        if raw is None:
            return (self.syllabify(normalized),) if normalized else ()
        alternatives = raw if isinstance(raw, list) and raw and isinstance(raw[0], Mapping) else [raw]
        results: list[tuple[SyllableCandidate, ...]] = []
        for alternative in alternatives:
            if not isinstance(alternative, Mapping):
                alternative = {"segments": alternative}
            results.append(self._alternative_candidates(normalized, alternative))
        return tuple(results)

    def _alternative_candidates(self, normalized: str, alternative: Any) -> tuple[SyllableCandidate, ...]:
        if not isinstance(alternative, Mapping):
            alternative = {"segments": alternative}
        evidence = _evidence(alternative.get("evidence"))
        segments = alternative.get("segments")
        if not isinstance(segments, Sequence) or "".join(map(str, segments)) != normalized:
            raise ValueError(f"override for {normalized!r} does not cover exact normalized text")
        return self._make_candidates(segments, evidence, str(alternative.get("notes", "")))

    @staticmethod
    def _make_candidates(
        segments: Sequence[Any], evidence: tuple[EvidenceRef, ...], notes: str
    ) -> tuple[SyllableCandidate, ...]:
        result: list[SyllableCandidate] = []
        cursor = 0
        for segment in segments:
            value = str(segment)
            end = cursor + len(value)
            result.append(
                SyllableCandidate(
                    text=value,
                    start=cursor,
                    end=end,
                    status=ResolutionStatus.RESOLVED,
                    evidence=evidence,
                    notes=notes,
                )
            )
            cursor = end
        return tuple(result)
