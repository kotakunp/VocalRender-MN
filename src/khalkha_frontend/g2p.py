"""Evidence-gated grapheme-to-phoneme resolution."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

import yaml

from .phones import PhoneRegistry
from .types import EvidenceRef, PhonemeCandidate, PronunciationOverride, ResolutionStatus


class G2PResolver(Protocol):
    def resolve(self, text: str, manual_override: Any = None, item_id: str | None = None) -> "G2PResult": ...


@dataclass(frozen=True)
class G2PResult:
    source_text: str
    phonemic: PhonemeCandidate
    layer: str
    diagnostics: tuple[str, ...] = ()


def _evidence(values: Any) -> tuple[EvidenceRef, ...]:
    result = []
    for entry in values or ():
        if isinstance(entry, EvidenceRef):
            result.append(entry)
            continue
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


def _override(raw: Any, identifier: str = "caller_override") -> PronunciationOverride:
    if isinstance(raw, PronunciationOverride):
        return raw
    if not isinstance(raw, Mapping):
        raise TypeError("manual override must be a PronunciationOverride or mapping")
    return PronunciationOverride(
        id=str(raw.get("id", identifier)),
        orthography=raw.get("orthography"),
        item_scope=raw.get("item_scope"),
        symbols=tuple(str(value) for value in raw.get("symbols", [])),
        level=str(raw.get("level", "phonemic")),
        evidence=_evidence(raw.get("evidence")),
        provenance=str(raw.get("provenance", "")),
        review_status=str(raw.get("review_status", "unreviewed")),
        expires=raw.get("expires"),
        notes=str(raw.get("notes", "")),
    )


class ConservativeG2PResolver:
    """Resolve only exact, evidence-backed entries; never map letters by default."""

    def __init__(
        self,
        overrides: Sequence[PronunciationOverride] = (),
        lexicon: Mapping[str, Mapping[str, Any]] | None = None,
        registry: PhoneRegistry | None = None,
    ) -> None:
        self.overrides = tuple(
            entry if isinstance(entry, PronunciationOverride) else _override(entry, f"override_{index + 1}")
            for index, entry in enumerate(overrides)
        )
        self.lexicon = dict(lexicon or {})
        self.registry = registry

    @classmethod
    def from_yaml(cls, path: str | Path, *, registry: PhoneRegistry | None = None) -> "ConservativeG2PResolver":
        location = Path(path)
        raw = yaml.safe_load(location.read_text(encoding="utf-8")) or {}
        entries = raw.get("overrides", [])
        if not isinstance(entries, list):
            raise ValueError("pronunciation overrides must be a list")
        return cls(
            tuple(_override(entry, f"override_{index + 1}") for index, entry in enumerate(entries)),
            registry=registry,
        )

    def resolve(self, text: str, manual_override: Any = None, item_id: str | None = None) -> G2PResult:
        normalized = unicodedata.normalize("NFC", text)
        if not normalized:
            return G2PResult(
                normalized,
                PhonemeCandidate(
                    None,
                    ResolutionStatus.RESEARCH_REQUIRED,
                    source_text=normalized,
                    notes="Empty input.",
                ),
                "unresolved",
                ("empty input",),
            )
        if manual_override is not None:
            entry = _override(manual_override)
            if not self._scope_matches(normalized, entry, item_id):
                return self._unresolved(normalized, "caller override scope does not match input", "caller override")
            return self._from_override(normalized, entry, "caller override", item_id)
        for entry in self.overrides:
            if entry.review_status == "reviewed" and self._scope_matches(normalized, entry, item_id):
                return self._from_override(normalized, entry, "reviewed pronunciation override", item_id)
        lexicon_entry = self.lexicon.get(normalized)
        if lexicon_entry is not None:
            level = str(lexicon_entry.get("level", "phonemic"))
            evidence = _evidence(lexicon_entry.get("evidence"))
            registry_id = lexicon_entry.get("registry_id")
            if registry_id is not None:
                if self.registry is None:
                    raise ValueError("lexicon registry_id requires an injected PhoneRegistry")
                if level != "phonemic":
                    raise ValueError("lexicon registry entries must be phonemic")
                if not isinstance(registry_id, str) or not registry_id.strip():
                    raise ValueError("lexicon registry_id must be non-empty")
                definition = self.registry.by_id(registry_id)
                if definition is None:
                    raise ValueError(f"lexicon registry_id {registry_id!r} is not registered")
                if definition.level != "phonemic":
                    raise ValueError("lexicon registry definition must be phonemic")
                if definition.status not in {ResolutionStatus.RESOLVED, ResolutionStatus.OVERRIDDEN}:
                    raise ValueError("lexicon registry definition must be resolved or overridden")
                if not definition.symbol or not definition.evidence:
                    raise ValueError("lexicon registry definition requires symbol and evidence")
                resolved_evidence = evidence + definition.evidence
                status = definition.status
                return G2PResult(
                    normalized,
                    PhonemeCandidate((definition.symbol,), status, resolved_evidence, normalized),
                    "evidence-backed phone registry",
                )
            symbols = tuple(str(value) for value in lexicon_entry.get("symbols", []))
            if level != "phonemic":
                return self._unresolved(normalized, "lexicon surface entry is not a phonemic value", "lexicon")
            if not evidence:
                raise ValueError(f"lexicon entry for {normalized!r} requires evidence")
            return G2PResult(
                normalized,
                PhonemeCandidate(symbols, ResolutionStatus.RESOLVED, evidence, normalized),
                "evidence-backed lexicon",
            )
        return self._unresolved(normalized, "no evidence-backed mapping registered", "unresolved")

    @staticmethod
    def _scope_matches(text: str, entry: PronunciationOverride, item_id: str | None) -> bool:
        if entry.orthography is not None and entry.orthography != text:
            return False
        if entry.item_scope is not None and entry.item_scope != item_id:
            return False
        return True

    @staticmethod
    def _from_override(text: str, entry: PronunciationOverride, layer: str, item_id: str | None) -> G2PResult:
        if not ConservativeG2PResolver._scope_matches(text, entry, item_id):
            return ConservativeG2PResolver._unresolved(text, "override scope does not match input", layer)
        if entry.level != "phonemic":
            return ConservativeG2PResolver._unresolved(text, "surface override is not reused as phonemic output", layer)
        return G2PResult(
            text,
            PhonemeCandidate(entry.symbols, ResolutionStatus.OVERRIDDEN, entry.evidence, text, entry.notes),
            layer,
        )

    @staticmethod
    def _unresolved(text: str, reason: str, layer: str) -> G2PResult:
        return G2PResult(
            text,
            PhonemeCandidate(None, ResolutionStatus.RESEARCH_REQUIRED, source_text=text, notes=reason),
            layer,
            (reason,),
        )
