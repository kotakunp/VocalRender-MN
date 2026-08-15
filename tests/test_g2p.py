import pytest

from khalkha_frontend.g2p import ConservativeG2PResolver
from khalkha_frontend.phones import PhoneDefinition, PhoneRegistry
from khalkha_frontend.types import EvidenceRef, ResolutionStatus

EVIDENCE = [{"id": "synthetic-g2p", "source": "tests/fixtures/synthetic"}]


def test_unknown_g2p_is_research_required() -> None:
    result = ConservativeG2PResolver().resolve("чамдаа")
    assert result.phonemic.symbols is None
    assert result.phonemic.status is ResolutionStatus.RESEARCH_REQUIRED
    assert result.layer == "unresolved"


def test_exact_manual_override_precedes_reviewed_override_and_lexicon() -> None:
    resolver = ConservativeG2PResolver(
        overrides=(
            {
                "id": "reviewed",
                "orthography": "abc",
                "symbols": ["reviewed"],
                "level": "phonemic",
                "review_status": "reviewed",
                "evidence": EVIDENCE,
            },
        ),
        lexicon={"abc": {"symbols": ["lexicon"], "evidence": EVIDENCE}},
    )
    result = resolver.resolve(
        "abc",
        {
            "orthography": "abc",
            "symbols": ["manual"],
            "level": "phonemic",
            "evidence": EVIDENCE,
        },
    )
    assert result.phonemic.symbols == ("manual",)
    assert result.phonemic.status is ResolutionStatus.OVERRIDDEN


def test_surface_override_is_not_reused_as_phonemic() -> None:
    result = ConservativeG2PResolver().resolve(
        "abc",
        {
            "orthography": "abc",
            "symbols": ["surface"],
            "level": "surface",
            "evidence": EVIDENCE,
        },
    )
    assert result.phonemic.symbols is None
    assert result.phonemic.status is ResolutionStatus.RESEARCH_REQUIRED


def test_lexicon_without_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires evidence"):
        ConservativeG2PResolver(lexicon={"abc": {"symbols": ["x"]}}).resolve("abc")


def test_missing_evidence_source_and_provenance_only_override_are_rejected() -> None:
    with pytest.raises(ValueError, match="id and source"):
        ConservativeG2PResolver().resolve(
            "abc",
            {"orthography": "abc", "symbols": ["x"], "evidence": [{"id": "e", "source": None}]},
        )
    with pytest.raises(ValueError, match="evidence reference"):
        ConservativeG2PResolver().resolve(
            "abc",
            {"orthography": "abc", "symbols": ["x"], "provenance": "caller record"},
        )


def test_item_scoped_override_requires_matching_item_id() -> None:
    resolver = ConservativeG2PResolver(
        overrides=(
            {
                "id": "item-only",
                "item_scope": "MNPHON_001",
                "symbols": ["scoped"],
                "evidence": EVIDENCE,
                "review_status": "reviewed",
            },
        )
    )
    assert resolver.resolve("abc").phonemic.symbols is None
    assert resolver.resolve("abc", item_id="MNPHON_002").phonemic.symbols is None
    result = resolver.resolve("abc", item_id="MNPHON_001")
    assert result.phonemic.symbols == ("scoped",)


def test_override_requires_all_declared_scopes() -> None:
    resolver = ConservativeG2PResolver(
        overrides=(
            {
                "id": "both-scopes",
                "orthography": "abc",
                "item_scope": "MNPHON_001",
                "symbols": ["scoped"],
                "evidence": EVIDENCE,
                "review_status": "reviewed",
            },
        )
    )
    assert resolver.resolve("other", item_id="MNPHON_001").phonemic.symbols is None
    assert resolver.resolve("abc", item_id="MNPHON_002").phonemic.symbols is None
    assert resolver.resolve("abc", item_id="MNPHON_001").phonemic.symbols == ("scoped",)


def test_registry_backed_lexicon_requires_resolved_phonemic_definition() -> None:
    definition = PhoneDefinition(
        "synthetic_phone",
        "P",
        "phonemic",
        (),
        ResolutionStatus.RESOLVED,
        (EvidenceRef("registry-evidence", "tests/fixtures/synthetic"),),
    )
    registry = PhoneRegistry((definition,))
    result = ConservativeG2PResolver(
        registry=registry,
        lexicon={"abc": {"registry_id": "synthetic_phone"}},
    ).resolve("abc")
    assert result.phonemic.symbols == ("P",)
    assert result.layer == "evidence-backed phone registry"

    with pytest.raises(ValueError, match="not registered"):
        ConservativeG2PResolver(registry=registry, lexicon={"abc": {"registry_id": "missing"}}).resolve("abc")

    surface = PhoneDefinition(
        "surface_phone",
        "S",
        "surface",
        (),
        ResolutionStatus.RESOLVED,
        (EvidenceRef("surface-evidence", "tests/fixtures/synthetic"),),
    )
    with pytest.raises(ValueError, match="must be phonemic"):
        ConservativeG2PResolver(
            registry=PhoneRegistry((surface,)), lexicon={"abc": {"registry_id": "surface_phone"}}
        ).resolve("abc")
