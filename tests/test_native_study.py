import itertools

from khalkha_frontend.benchmark import BenchmarkItem, Lexicality
from khalkha_frontend.evidence import load_evidence_registry
from khalkha_frontend.native_study import ContextAnnotation, Quota, hash_item, select_group, validate_source_span


def _item(item_id: str, number: int = 1, group: str = "L"):
    return BenchmarkItem(item_id, number, item_id, group, "fixture", Lexicality.LEXICAL)


def test_hash_uses_exact_nfc_namespace():
    assert len(hash_item("MNPHON_001")) == 64
    assert hash_item("MNPHON_001") == hash_item("MNPHON_001")


def test_selection_meets_required_context_before_hash_tie_break():
    ids = [f"MNPHON_{i:03d}" for i in range(1, 9)]
    manifest = type("Manifest", (), {"items": tuple(_item(item_id, i) for i, item_id in enumerate(ids, 1))})()
    annotations = {
        item_id: ContextAnnotation(
            item_id,
            ("word_initial" if i == 1 else "word_final",),
            ("front",),
            (),
            "л",
            (),
            None,
            "reviewer",
            "2026-08-15",
            "approved",
        )
        for i, item_id in enumerate(ids, 1)
    }
    quotas = (Quota("initial", "L", "structural_context", ("word_initial",), 1, True),)
    result = select_group("L", manifest, annotations, quotas, size=8, fields=("structural_context",))
    assert result["selected_ids"] == ids
    assert result["diversity_vector"] == [2]


def test_alignment_spans_reconstruct_raw_cyrillic():
    validate_source_span("хүүхэд", [{"text": "хүү", "source_span": [0, 3]}, {"text": "хэд", "source_span": [3, 6]}])


def test_evidence_registry_accepts_multiple_explicit_uses(tmp_path):
    path = tmp_path / "evidence.yaml"
    path.write_text(
        """evidence:
  - id: source-1
    claim: reviewed claim
    source_type: publication
    citation: citation
    language_variety: standard-khalkha
    locator: p.1
    review_status: reviewed
    allowed_use: [context_annotation, pronunciation]
""",
        encoding="utf-8",
    )
    assert set(load_evidence_registry(path)["source-1"]["allowed_use"]) == {
        "context_annotation",
        "pronunciation",
    }


def test_dynamic_programming_selector_matches_bruteforce():
    ids = [f"MNPHON_{i:03d}" for i in range(1, 11)]
    manifest = type("Manifest", (), {"items": tuple(_item(item_id, i) for i, item_id in enumerate(ids, 1))})()
    annotations = {
        item_id: ContextAnnotation(
            item_id,
            (("word_initial",) if i % 3 == 0 else ("word_final",)),
            (("front",) if i % 2 == 0 else ("back",)),
            (),
            f"c{i % 4}",
            (),
            None,
            "reviewer",
            "2026-08-15",
            "approved",
        )
        for i, item_id in enumerate(ids, 1)
    }
    quotas = (Quota("initial", "L", "structural_context", ("word_initial",), 1, True),)
    result = select_group(
        "L",
        manifest,
        annotations,
        quotas,
        size=4,
        fields=("structural_context", "vowel_context_class", "target_consonant"),
    )
    feasible = [
        combo
        for combo in itertools.combinations(ids, 4)
        if any("word_initial" in annotations[item_id].structural_context for item_id in combo)
    ]
    best_vector = max(
        tuple(
            len({value for item_id in combo for value in annotations[item_id].values(field)})
            for field in (
                "structural_context",
                "vowel_context_class",
                "target_consonant",
            )
        )
        for combo in feasible
    )
    tied = [
        combo
        for combo in feasible
        if tuple(
            len({value for item_id in combo for value in annotations[item_id].values(field)})
            for field in (
                "structural_context",
                "vowel_context_class",
                "target_consonant",
            )
        )
        == best_vector
    ]
    expected = min(
        tied,
        key=lambda combo: tuple(sorted(hash_item(item_id) for item_id in combo)) + tuple(sorted(combo)),
    )
    assert result["feasible_sets"] == len(feasible)
    assert tuple(result["diversity_vector"]) == best_vector
    assert tuple(result["selected_ids"]) == tuple(sorted(expected))
