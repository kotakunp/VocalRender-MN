"""Incomplete phone inventory with evidence-gated resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from .types import EvidenceRef, ResolutionStatus


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


@dataclass(frozen=True)
class PhoneDefinition:
    id: str
    symbol: str | None
    level: str
    articulatory_tags: tuple[str, ...]
    status: ResolutionStatus
    evidence: tuple[EvidenceRef, ...]
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "articulatory_tags", tuple(self.articulatory_tags))
        object.__setattr__(self, "evidence", _evidence(self.evidence))
        self.validate()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], index: int) -> "PhoneDefinition":
        try:
            status = ResolutionStatus(str(raw.get("status", "research_required")))
        except ValueError as exc:
            raise ValueError(f"phones[{index}].status: {exc}") from exc
        result = cls(
            id=str(raw["id"]),
            symbol=None if raw.get("symbol") is None else str(raw["symbol"]),
            level=str(raw.get("level", "phonemic")),
            articulatory_tags=tuple(str(value) for value in raw.get("articulatory_tags", [])),
            status=status,
            evidence=_evidence(raw.get("evidence", [])),
            notes=str(raw.get("notes", "")),
        )
        return result

    def validate(self, label: str = "phone") -> None:
        if not self.id.strip():
            raise ValueError(f"{label}.id must be non-empty")
        if self.level not in {"phonemic", "surface"}:
            raise ValueError(f"{label}.level must be phonemic or surface")
        if self.symbol is not None and not self.symbol.strip():
            raise ValueError(f"{label}.symbol must be non-empty when present")
        if self.symbol is not None and (
            self.status not in {ResolutionStatus.RESOLVED, ResolutionStatus.OVERRIDDEN} or not self.evidence
        ):
            raise ValueError(f"{label}.symbol requires evidence and a resolved status")


class PhoneRegistry:
    def __init__(self, definitions: tuple[PhoneDefinition, ...], source_path: Path | None = None) -> None:
        self.definitions = definitions
        self.source_path = source_path
        self._by_id = {definition.id: definition for definition in definitions}
        self._by_symbol = {definition.symbol: definition for definition in definitions if definition.symbol is not None}
        self.validate()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], source_path: Path | None = None) -> "PhoneRegistry":
        if int(raw.get("schema_version", 0)) != 1:
            raise ValueError("phone inventory schema_version must be 1")
        entries = raw.get("phones", [])
        if not isinstance(entries, list):
            raise ValueError("phone inventory phones must be a list")
        return cls(
            tuple(PhoneDefinition.from_mapping(entry, index) for index, entry in enumerate(entries)),
            source_path,
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PhoneRegistry":
        location = Path(path)
        raw = yaml.safe_load(location.read_text(encoding="utf-8")) or {}
        return cls.from_mapping(raw, location)

    def validate(self) -> None:
        if len(self._by_id) != len(self.definitions):
            raise ValueError("phone inventory contains duplicate IDs")
        symbols = [definition.symbol for definition in self.definitions if definition.symbol is not None]
        if len(set(symbols)) != len(symbols):
            raise ValueError("phone inventory contains duplicate symbols")

    def by_id(self, identifier: str) -> PhoneDefinition | None:
        return self._by_id.get(identifier)

    get_by_id = by_id

    def by_symbol(self, symbol: str) -> PhoneDefinition | None:
        return self._by_symbol.get(symbol)

    get_by_symbol = by_symbol

    def __len__(self) -> int:
        return len(self.definitions)
