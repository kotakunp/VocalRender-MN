from pathlib import Path

import pytest

from khalkha_frontend.phones import PhoneDefinition, PhoneRegistry
from khalkha_frontend.types import EvidenceRef, PhonemeCandidate, PhoneCandidate, ResolutionStatus

ROOT = Path(__file__).resolve().parents[1]


def test_production_inventory_is_incomplete_by_design() -> None:
    registry = PhoneRegistry.from_yaml(ROOT / "resources" / "phonology" / "phone_inventory.yaml")
    assert len(registry) >= 5
    assert all(definition.symbol is None for definition in registry.definitions)


def test_resolved_inventory_entry_requires_evidence() -> None:
    with pytest.raises(ValueError, match="requires evidence"):
        PhoneRegistry.from_mapping(
            {
                "schema_version": 1,
                "phones": [
                    {
                        "id": "synthetic",
                        "symbol": "S",
                        "level": "phonemic",
                        "status": "resolved",
                        "evidence": [],
                    }
                ],
            }
        )


def test_missing_evidence_source_is_rejected() -> None:
    with pytest.raises(ValueError, match="id and source"):
        PhoneRegistry.from_mapping(
            {
                "schema_version": 1,
                "phones": [
                    {
                        "id": "synthetic",
                        "symbol": "S",
                        "level": "phonemic",
                        "status": "resolved",
                        "evidence": [{"id": "e", "source": None}],
                    }
                ],
            }
        )


def test_nonempty_symbols_and_evidence_are_required_for_resolved_values() -> None:
    evidence = (EvidenceRef("e", "tests/fixtures/synthetic"),)
    with pytest.raises(ValueError, match="non-empty symbols"):
        PhonemeCandidate((), ResolutionStatus.RESOLVED, evidence, "abc")
    with pytest.raises(ValueError, match="non-empty symbols"):
        PhoneCandidate((), ResolutionStatus.OVERRIDDEN, evidence)
    with pytest.raises(ValueError, match="non-empty"):
        PhoneDefinition("empty", "", "phonemic", (), ResolutionStatus.RESOLVED, evidence)
    with pytest.raises(ValueError, match="requires evidence"):
        PhoneDefinition("unbacked", "P", "phonemic", (), ResolutionStatus.UNRESOLVED, ())
