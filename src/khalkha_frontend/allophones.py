"""Evidence-gated, deterministic allophone resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .types import EvidenceRef, PhoneCandidate, PhonemeCandidate, ResolutionStatus, _freeze


@dataclass(frozen=True)
class PhonologicalEnvironment:
    left_phone_id: str | None = None
    right_phone_id: str | None = None
    word_boundary: str | None = None
    morpheme_boundary: str | None = None
    position: str | None = None
    score_context: str | None = None

    def as_mapping(self) -> dict[str, Any]:
        return {
            "left_phone_id": self.left_phone_id,
            "right_phone_id": self.right_phone_id,
            "word_boundary": self.word_boundary,
            "morpheme_boundary": self.morpheme_boundary,
            "position": self.position,
            "score_context": self.score_context,
        }


def _evidence(values: Any) -> tuple[EvidenceRef, ...]:
    result = []
    for entry in values or ():
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
                    id=entry["id"],
                    source=source,
                    kind=str(entry.get("kind", "")),
                )
            )
    return tuple(result)


@dataclass(frozen=True)
class AllophoneRule:
    id: str
    priority: int
    input_phone_id: str
    output_phone_id: str
    conditions: Mapping[str, Any] = field(default_factory=dict)
    evidence: tuple[EvidenceRef, ...] = field(default_factory=tuple)
    status: ResolutionStatus = ResolutionStatus.RESEARCH_REQUIRED

    def __post_init__(self) -> None:
        if self.status not in {ResolutionStatus.RESOLVED, ResolutionStatus.OVERRIDDEN}:
            raise ValueError("active allophone rules must be resolved or overridden")
        if not self.id.strip() or not self.input_phone_id.strip() or not self.output_phone_id.strip():
            raise ValueError("allophone rule id and phone IDs must be non-empty")
        evidence = _evidence(self.evidence)
        if not evidence:
            raise ValueError("resolved allophone rules require evidence")
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "conditions", _freeze(self.conditions))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], index: int) -> "AllophoneRule":
        status = ResolutionStatus(str(raw.get("status", "research_required")))
        if status == ResolutionStatus.RESEARCH_REQUIRED:
            raise ValueError(f"rules[{index}] research_required rules must remain out of active list")
        return cls(
            id=str(raw["id"]),
            priority=int(raw.get("priority", 0)),
            input_phone_id=str(raw["input_phone_id"]),
            output_phone_id=str(raw["output_phone_id"]),
            conditions=dict(raw.get("conditions", {})),
            evidence=_evidence(raw.get("evidence", [])),
            status=status,
        )

    def matches(self, environment: PhonologicalEnvironment) -> bool:
        values = environment.as_mapping()
        return all(values.get(key) == value for key, value in self.conditions.items())


class AllophoneResolver:
    def __init__(self, rules: Iterable[AllophoneRule] = ()) -> None:
        self.rules = tuple(sorted(rules, key=lambda rule: (-rule.priority, rule.id)))
        self._validate_conflicts()

    def _validate_conflicts(self) -> None:
        seen: dict[tuple[int, str, tuple[tuple[str, Any], ...]], str] = {}
        for rule in self.rules:
            key = (rule.priority, rule.input_phone_id, tuple(sorted(rule.conditions.items())))
            previous = seen.get(key)
            if previous is not None and previous != rule.output_phone_id:
                raise ValueError(f"conflicting allophone rules at priority {rule.priority}: {rule.id}")
            seen[key] = rule.output_phone_id

    def resolve(
        self,
        phonemic: PhonemeCandidate,
        environment: PhonologicalEnvironment | None = None,
        surface_override: PhoneCandidate | None = None,
    ) -> PhoneCandidate:
        if surface_override is not None:
            if surface_override.status not in {ResolutionStatus.OVERRIDDEN, ResolutionStatus.RESOLVED}:
                raise ValueError("surface override must be resolved or overridden")
            if not surface_override.evidence:
                raise ValueError("surface override requires evidence")
            return surface_override
        environment = environment or PhonologicalEnvironment()
        if phonemic.symbols is None:
            return PhoneCandidate(
                None,
                ResolutionStatus.RESEARCH_REQUIRED,
                phonemic.evidence,
                environment.as_mapping(),
                "phonemic candidate is unresolved",
            )
        if not self.rules:
            return PhoneCandidate(
                phonemic.symbols,
                ResolutionStatus.UNRESOLVED,
                phonemic.evidence,
                environment.as_mapping(),
                "no reviewed allophone rules; surface realization remains unresolved",
            )
        output: list[str] = []
        evidence: list[EvidenceRef] = list(phonemic.evidence)
        changed = False
        for symbol in phonemic.symbols:
            match = next(
                (rule for rule in self.rules if rule.input_phone_id == symbol and rule.matches(environment)),
                None,
            )
            if match is None:
                output.append(symbol)
            else:
                output.append(match.output_phone_id)
                evidence.extend(match.evidence)
                changed = True
        if not changed:
            return PhoneCandidate(
                tuple(output),
                ResolutionStatus.UNRESOLVED,
                tuple(evidence),
                environment.as_mapping(),
                "no matching reviewed allophone rule",
            )
        return PhoneCandidate(tuple(output), ResolutionStatus.RESOLVED, tuple(evidence), environment.as_mapping())
