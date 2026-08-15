from pathlib import Path

from khalkha_frontend.tokenizer_audit import (
    AuditSample,
    aggregate_records,
    aggregate_by_benchmark_group,
    aggregate_by_character,
    aggregate_by_word_length,
    collect_benchmark,
    collect_unimorph,
    collect_special_probes,
    percentile,
    sha256_file,
    tokenize_sample,
)


class FakeTokenizer:
    unk_token = "<unk>"
    unk_token_id = 99
    all_special_tokens = ("<unk>",)

    def __call__(self, text, **kwargs):
        return {"input_ids": [99 if "¤" in text else index + 1 for index, _ in enumerate(text)]}

    def convert_ids_to_tokens(self, token_ids):
        return ["<unk>" if item == 99 else f"t{item}" for item in token_ids]

    def decode(self, token_ids, **kwargs):
        return "mismatch" if 99 in token_ids else "хэл"

    def __len__(self):
        return 100


def test_empty_and_special_probe_metrics():
    record = tokenize_sample(FakeTokenizer(), AuditSample("test", "empty", "", ""))
    assert record.character_count == 0
    assert record.tokens_per_character == 0
    assert aggregate_records([record])["count"] == 1
    assert len(collect_special_probes()) == 10


def test_special_character_aggregates_and_hash(tmp_path: Path):
    records = [tokenize_sample(FakeTokenizer(), sample) for sample in collect_special_probes()]
    assert set(aggregate_by_character(records)) == set("ӨөҮүЁёЬьЪъ")
    path = tmp_path / "input.txt"
    path.write_text("abc", encoding="utf-8")
    assert sha256_file(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_unknown_roundtrip_and_codepoints():
    record = tokenize_sample(FakeTokenizer(), AuditSample("test", "one", "¤", "¤"))
    assert record.has_unknown
    assert record.roundtrip_mismatch
    assert record.code_points == ("U+00A4",)


def test_percentile_values():
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
    assert percentile([], 0.5) is None


def test_benchmark_collector_includes_all_ids(tmp_path: Path):
    path = tmp_path / "manifest.yaml"
    path.write_text("sections:\n  L:\n    carrier_CV:\n      001: ла\n      002: лэ\n", encoding="utf-8")
    samples = collect_benchmark(path)
    assert [sample.source_item_id for sample in samples] == ["benchmark:001", "benchmark:002"]
    assert all(sample.target_group == "L" for sample in samples)


def test_canonical_benchmark_items_are_supported(tmp_path: Path):
    path = tmp_path / "manifest.yaml"
    path.write_text(
        "schema_version: 2\nitems:\n  - id: MNPHON_001\n    text: ла\n    target_group: L\n"
        "  - id: MNPHON_002\n    text: ха\n    target_group: H\n",
        encoding="utf-8",
    )
    samples = collect_benchmark(path)
    assert [sample.source_item_id for sample in samples] == ["benchmark:MNPHON_001", "benchmark:MNPHON_002"]
    assert [sample.target_group for sample in samples] == ["L", "H"]


def test_unimorph_sampling_is_even_and_includes_endpoints():
    class Row:
        def __init__(self, index):
            self.source_line = index + 1
            self.surface = f"үг{index}"

    class Resource:
        def iter_analyses(self):
            return iter(Row(index) for index in range(11))

    samples = collect_unimorph(Resource(), 5)
    assert [sample.source_item_id for sample in samples] == [
        "unimorph_surface:000001",
        "unimorph_surface:000004",
        "unimorph_surface:000006",
        "unimorph_surface:000009",
        "unimorph_surface:000011",
    ]


def test_unimorph_sampling_includes_surface_and_lemma_sources():
    class Resource:
        def iter_analyses(self):
            return iter(type("Row", (), {"source_line": index + 1, "surface": f"үг{index}"})() for index in range(6))

        def iter_segmentations(self):
            return iter(type("Row", (), {"source_line": index + 10, "lemma": f"яз{index}"})() for index in range(6))

    samples = collect_unimorph(Resource(), 6)
    assert [sample.source for sample in samples] == [
        "unimorph_surface",
        "unimorph_surface",
        "unimorph_surface",
        "unimorph_lemma",
        "unimorph_lemma",
        "unimorph_lemma",
    ]
    assert samples[0].source_item_id == "unimorph_surface:000001"
    assert samples[-1].source_item_id == "unimorph_lemma:000015"


def test_aggregates_cover_group_and_word_length():
    records = [
        tokenize_sample(FakeTokenizer(), AuditSample("benchmark", "1", "ла", "ла", "L")),
        tokenize_sample(FakeTokenizer(), AuditSample("benchmark", "2", "хүүхэд", "хүүхэд", "H")),
    ]
    assert set(aggregate_by_benchmark_group(records)) == {"L", "H"}
    assert set(aggregate_by_word_length(records)) == {"1-3", "4-7"}
