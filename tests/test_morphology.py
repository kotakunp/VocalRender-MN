from pathlib import Path

import pytest

from khalkha_frontend.morphology import (
    MorphologyFormatError,
    UniMorphKhalkha,
)


def resource(tmp_path: Path) -> Path:
    directory = tmp_path / "unimorph_khk"
    directory.mkdir()
    (directory / "khk").write_text("нэр\tнэрийн\tN;GEN;SG\nнэр\tнэрийн\tN;GEN;SG\n", encoding="utf-8")
    (directory / "khk.segmentations").write_text("нэр\tнэрийн\tN|GEN;SG\tнэр|ийн\n", encoding="utf-8")
    (directory / "khk.derivations").write_text("үер\tүерлэх\tN\tV\tлэх\tsuffix\n", encoding="utf-8")
    return directory


def test_known_lookup_preserves_duplicates_and_boundaries(tmp_path):
    lookup = UniMorphKhalkha(resource(tmp_path)).lookup(" НЭРИЙН ")
    assert lookup.known
    assert len(lookup.analyses) == 2
    assert lookup.segmentations[0].morphemes == ("нэр", "ийн")
    assert lookup.analyses[0].source_line == 1


def test_oov_is_explicit_and_empty(tmp_path):
    result = UniMorphKhalkha(resource(tmp_path)).lookup("байхгүй")
    assert result.known is False
    assert result.analyses == ()
    assert result.segmentations == ()


def test_derivations_are_lossless_raw_rows(tmp_path):
    row = next(UniMorphKhalkha(resource(tmp_path)).iter_derivations())
    assert row.fields == ("үер", "үерлэх", "N", "V", "лэх", "suffix")


def test_iterators_honor_zero_and_negative_limits(tmp_path):
    resource_instance = UniMorphKhalkha(resource(tmp_path))
    assert list(resource_instance.iter_analyses(limit=0)) == []
    assert list(resource_instance.iter_segmentations(limit=0)) == []
    assert list(resource_instance.iter_derivations(limit=0)) == []
    for iterator in (
        resource_instance.iter_analyses,
        resource_instance.iter_segmentations,
        resource_instance.iter_derivations,
    ):
        with pytest.raises(ValueError, match="non-negative"):
            list(iterator(limit=-1))


def test_malformed_rows_raise_actionable_error(tmp_path):
    directory = resource(tmp_path)
    (directory / "khk").write_text("нэр\tнэрийн\n", encoding="utf-8")
    with pytest.raises(MorphologyFormatError, match="khk:1"):
        UniMorphKhalkha(directory).lookup("нэрийн")


def test_source_is_not_mutated(tmp_path):
    directory = resource(tmp_path)
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    UniMorphKhalkha(directory).lookup("нэрийн")
    assert before == {path.name: path.read_bytes() for path in directory.iterdir()}
