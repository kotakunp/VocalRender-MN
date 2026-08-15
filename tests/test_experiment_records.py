"""Validation for checked-in Milestone 0 experiment evidence."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
RUN_REQUIRED = {
    "schema_version",
    "run_id",
    "status",
    "experiment",
    "command",
    "git_sha",
    "started_at",
    "finished_at",
    "environment",
    "inputs",
    "outputs",
    "warnings",
    "blocker",
    "notes",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|/(?:home|Users)/)")


def _load(path: Path):
    with path.open(encoding="utf-8") as handle:
        if path.suffix == ".json":
            return json.load(handle)
        return yaml.safe_load(handle)


def test_experiment_directories_follow_contract() -> None:
    for number in range(1, 6):
        directory = next(EXPERIMENTS.glob(f"{number:03d}_*"))
        assert (directory / "README.md").is_file()
        if number < 5:
            assert (directory / "config").is_dir()
            assert (directory / "results" / "run.json").is_file()
        else:
            assert sorted(path.name for path in directory.iterdir()) == ["README.md"]


def test_all_experiment_json_and_yaml_parse() -> None:
    files = sorted(
        path for path in EXPERIMENTS.rglob("*") if path.is_file() and path.suffix.lower() in {".json", ".yaml", ".yml"}
    )
    assert files
    for path in files:
        assert _load(path) is not None, path


def test_run_records_are_schema_versioned_and_sanitized() -> None:
    records = sorted(EXPERIMENTS.glob("00[1-4]_*/results/run.json"))
    assert len(records) == 4
    for path in records:
        record = _load(path)
        assert RUN_REQUIRED <= set(record), path
        assert record["schema_version"] == "milestone-run/v1"
        assert record["status"] in {"success", "blocked", "failed"}
        assert re.fullmatch(r"[0-9a-f]{40}", record["git_sha"])
        assert isinstance(record["warnings"], list)
        assert isinstance(record["inputs"], list)
        assert isinstance(record["outputs"], list)
        if record["status"] == "blocked":
            assert record["blocker"]
            assert record["outputs"] == []
        elif record["status"] == "success":
            assert record["blocker"] is None
        for artifact in [*record["inputs"], *record["outputs"]]:
            artifact_path = artifact["path"]
            assert not PurePosixPath(artifact_path).is_absolute()
            assert not ABSOLUTE_PATH.search(artifact_path)
            assert SHA256.fullmatch(artifact["sha256"])


def test_experiment_and_report_text_contains_no_assembly_paths_or_secrets() -> None:
    checked = [ROOT / "README.md", *EXPERIMENTS.rglob("*"), *(ROOT / "reports").rglob("*")]
    forbidden = ("__GET__", "__MAKE__", "gho_", "github_pat_", "C:\\Users\\", "/home/")
    for path in checked:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        for marker in forbidden:
            assert marker not in text, f"{marker!r} found in {path.relative_to(ROOT)}"
