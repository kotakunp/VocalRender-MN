# fmt: off

from pathlib import Path

from khalkha_frontend import ResourcePaths


def _make_resources(root: Path):
    for relative in (
        "resources/unimorph_khk",
        "resources/lexicon",
        "resources/phonology",
    ):
        (root / relative).mkdir(parents=True)


def test_injected_repository_root_resolves_semantic_paths(tmp_path):
    _make_resources(tmp_path)
    paths = ResourcePaths.from_repository_root(tmp_path)

    assert paths.root == tmp_path.resolve()
    assert paths.unimorph_khk == tmp_path / "resources/unimorph_khk"
    assert paths.validate() == ()


def test_missing_layout_returns_structured_problems(tmp_path):
    paths = ResourcePaths.from_repository_root(tmp_path)

    problems = paths.validate(require_raw_data=True)

    assert all(
        problem.path.is_absolute() and problem.message for problem in problems
    )
    assert paths.speech in {problem.path for problem in problems}


def test_optional_raw_directories_are_not_required(tmp_path):
    _make_resources(tmp_path)
    paths = ResourcePaths.from_repository_root(tmp_path)

    assert paths.validate() == ()
    assert paths.validate(require_raw_data=True)


def test_legacy_marker_tree_is_not_a_fallback(tmp_path):
    (tmp_path / "resources/__GET__unimorph_khk").mkdir(parents=True)
    paths = ResourcePaths.from_repository_root(tmp_path)

    assert paths.unimorph_khk == tmp_path / "resources/unimorph_khk"
    assert paths.validate()

# fmt: on
