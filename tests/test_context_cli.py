import json
from pathlib import Path
import subprocess
import sys


def test_context_cli_applies_config_and_is_deterministic(tmp_path: Path):
    resources = tmp_path / "resources"
    (resources / "lexicon").mkdir(parents=True)
    (resources / "lexicon" / "most_frequent_words.csv").write_text(
        "word,frequency\nмал, 0.5\nхэл, 0.4\n", encoding="utf-8"
    )
    config = tmp_path / "context.yaml"
    config.write_text("groups: [L]\nsource: frequency\nlimit_per_pattern: 10\ngenerated_at: fixed\n", encoding="utf-8")
    script = Path(__file__).parents[1] / "scripts" / "mn" / "mine_contexts.py"
    outputs = []
    for index in range(2):
        output = tmp_path / f"run-{index}.json"
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--resources-root",
                str(resources),
                "--config",
                str(config),
                "--output-json",
                str(output),
            ],
            check=True,
        )
        outputs.append(json.loads(output.read_text(encoding="utf-8")))
    assert outputs[0] == outputs[1]
    assert outputs[0]["groups"] == ["L"]
    assert outputs[0]["generated_at"] == "fixed"
    assert str(config) not in output.read_text(encoding="utf-8")
