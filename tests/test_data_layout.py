from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATHS = (
    ROOT / "resources/manifest.yaml",
    ROOT / "data/raw/manifest.yaml",
)
REQUIRED_FIELDS = {
    "id",
    "name",
    "local_path",
    "source_url",
    "upstream_repository",
    "version_or_revision",
    "acquired_on",
    "license",
    "redistribution",
    "training_use",
    "research_evaluation_use",
    "contains_personal_data",
    "checksums",
    "notes",
}


def _load_manifests():
    return [yaml.safe_load(path.read_text(encoding="utf-8")) for path in MANIFEST_PATHS]


def _resources():
    return [resource for manifest in _load_manifests() for resource in manifest["resources"]]


def test_manifests_have_schema_version_one():
    assert all(manifest["schema_version"] == 1 for manifest in _load_manifests())


def test_manifest_paths_are_unique_and_never_use_assembly_markers():
    resources = _resources()
    local_paths = [resource["local_path"] for resource in resources]

    assert len({resource["id"] for resource in resources}) == len(resources)
    assert len(set(local_paths)) == len(local_paths)
    assert all("__GET__" not in path and "__MAKE__" not in path for path in local_paths)


def test_manifest_entries_have_explicit_rights_fields():
    for resource in _resources():
        assert REQUIRED_FIELDS <= resource.keys()
        assert {"identifier", "source"} <= resource["license"].keys()
        assert resource["redistribution"] in {
            "allowed",
            "prohibited",
            "unknown",
        }
        assert resource["training_use"] in {"allowed", "prohibited", "unknown"}
        assert resource["research_evaluation_use"] in {
            "allowed",
            "prohibited",
            "unknown",
        }


def test_semantic_resource_directories_exist():
    for path in (
        ROOT / "resources/unimorph_khk",
        ROOT / "resources/lexicon",
        ROOT / "resources/phonology",
    ):
        assert path.is_dir()
    assert (ROOT / "benchmarks/MN-PHON-250").is_dir()


@pytest.mark.parametrize(
    "relative_path",
    (
        "data/raw/speech",
        "data/raw/benchmark_tts",
        "data/raw/native_speech",
        "data/raw/native_singing",
        "data/raw/music3",
    ),
)
def test_raw_collection_directories_are_optional_in_clean_clones(
    relative_path,
):
    path = ROOT / relative_path
    assert not path.exists() or path.is_dir()


def test_tracked_paths_have_no_marker_directories():
    git_dir = ROOT / ".git"
    if not git_dir.exists():
        pytest.skip("git metadata is unavailable in this source archive")
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert all("__GET__" not in path and "__MAKE__" not in path for path in result.stdout.splitlines())


def test_tracked_files_do_not_include_audio_or_checkpoints():
    git_dir = ROOT / ".git"
    if not git_dir.exists():
        pytest.skip("git metadata is unavailable in this source archive")
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    forbidden = {
        ".wav",
        ".flac",
        ".mp3",
        ".ogg",
        ".opus",
        ".pth",
        ".safetensors",
        ".ckpt",
    }
    allowed_audio_prefixes = ("assets/audio/", "examples/prompt_audio/")
    assert all(
        Path(path).suffix.lower() not in forbidden or path.startswith(allowed_audio_prefixes)
        for path in result.stdout.splitlines()
    )
