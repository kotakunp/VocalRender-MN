# Plan 001: Establish a deterministic Milestone 0 verification baseline

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the STOP conditions occurs, stop and report; do not
> improvise. When done, update this plan's row in `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat c0ab96e..HEAD -- pyproject.toml .github/workflows tests`
> If any in-scope file changed since this plan was written, compare the current
> state below against the live files before proceeding. A semantic mismatch is
> a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: tests / DX
- **Planned at**: commit `c0ab96e`, 2026-08-15

## Why this matters

Milestone 0 will move user data, add a second Python package, and introduce
schemas whose main value is preventing unsupported linguistic claims. The repo
currently has no `tests/` directory and no Python CI, so executors otherwise
have no reliable regression gate. Establish a small upstream score-contract
suite first and make every later plan use the same commands.

## Current state

- `.github/workflows/pages.yml` is the only workflow. It copies `docs/` and
  `assets/` into a Pages artifact; it does not install Python or run tests.
- `pyproject.toml:23` requires Python `>=3.10` and `.python-version` contains
  `3.10`.
- `pyproject.toml:55-59` already defines the `dev` extra:

  ```toml
  dev = [
      "pytest>=6.0",
      "black>=21.0",
      "flake8>=3.8",
  ]
  ```

- `pyproject.toml:84-99` configures Black for Python 3.10 and line length 120.
- There is no pytest configuration and no test directory.
- `src/vocalrender/training/svs_raw_data.py:34-91` defines the upstream contract
  that maps `word`, `pitch`, `note`, and `pitch2word` into syllable records. It
  deliberately preserves one lyric unit across multiple notes as a list:

  ```python
  if len(pitch_indices) == 1:
      syllables.append({"char": word, "pitch": pitch, "note": note})
  else:
      syllables.append({
          "char": word,
          "pitch": pitch_list,
          "note": note_list,
      })
  ```

- `src/vocalrender/training/svs_raw_data.py:103-130` expands melisma while
  retaining a shared `word_idx`. This is the score-control behavior the
  Mongolian adapter must not break.
- The planning shell did not have `python` or `uv` on `PATH`. This is an
  environment fact, not a repository failure; verification may only be marked
  successful after an executor activates a supported Python environment.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Create environment (Windows) | `py -3.10 -m venv .venv` | exit 0; `.venv/` exists |
| Activate (PowerShell) | `.\.venv\Scripts\Activate.ps1` | prompt uses `.venv` |
| Install | `python -m pip install -e ".[dev]"` | exit 0; editable `vocalrender` installed |
| Tests | `python -m pytest -q` | exit 0; all collected tests pass |
| Format check | `python -m black --check tests` | exit 0; no reformat needed |
| Lint | `python -m flake8 tests` | exit 0; no findings |

On Linux/macOS, create with `python3.10 -m venv .venv`, activate with
`source .venv/bin/activate`, then use the same `python -m ...` commands.

## Scope

**In scope (the only files to modify):**

- `pyproject.toml`
- `.github/workflows/ci.yml` (create)
- `tests/test_upstream_score_contract.py` (create)

**Out of scope:**

- Any runtime file under `src/vocalrender/`; this plan characterizes behavior
  and must not change it.
- CUDA/model-loading tests, inference, training, and checkpoint access.
- Coverage thresholds; the initial suite is a contract baseline, not a claim of
  broad upstream coverage.
- Adding new test/lint frameworks beyond existing `pytest`, Black, and flake8.

## Git workflow

- Branch: `codex/001-verification-baseline`
- Commit: one logical commit, suggested message
  `test: establish VocalRender-MN verification baseline`.
- Do not push or open a PR unless the operator explicitly requests it.

## Steps

### Step 1: Add deterministic pytest configuration

Append `[tool.pytest.ini_options]` to `pyproject.toml` with:

- `testpaths = ["tests"]`
- `addopts = "--strict-markers --strict-config"`
- a registered `integration` marker whose description says it may require
  local checkpoints/GPU and is excluded from ordinary unit verification.

Do not alter project dependencies or the existing Black configuration.

**Verify**:
`python -m pytest --help` -> exit 0 with no pytest configuration warning.

### Step 2: Characterize the upstream score mapping

Create `tests/test_upstream_score_contract.py`. Import
`convert_annotation_to_syllables` and `expand_syllables` from
`vocalrender.training.svs_raw_data`. Add focused tests for:

1. one Mongolian lyric unit mapped to one note;
2. one multi-character lyric unit such as `"хайр"` preserved as one unit (not
   split into characters);
3. melisma where one lyric unit maps to two notes and expands into two rows
   with the same `word_idx`;
4. two identical adjacent lyric strings mapped to distinct notes and distinct
   `word_idx` values;
5. an unmapped lyric unit following the current behavior (it is skipped), so a
   future adapter can reject the input before upstream silently skips it.

Use small literal lists only; no checkpoint or audio fixture. Assert complete
structures rather than merely lengths.

**Verify**:
`python -m pytest -q tests/test_upstream_score_contract.py` -> five tests pass.

### Step 3: Add Python CI without touching the Pages workflow

Create `.github/workflows/ci.yml` triggered by pull requests and pushes to
`main`. Use `actions/checkout@v4`, `actions/setup-python@v5`, and a matrix for
Python 3.10 and 3.11. Install with:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run `python -m pytest -q`. Run Black and flake8 only over paths that exist so
later plans can add `src/khalkha_frontend` and `scripts/mn` without editing the
workflow again. A small Bash step may assemble a `targets` array beginning with
`tests` and append either directory when present, then execute:

```bash
python -m black --check "${targets[@]}"
python -m flake8 "${targets[@]}"
```

Do not run model inference in CI and do not modify `pages.yml`.

**Verify**:

- Parse the YAML using the already required PyYAML:
  `python -c "import pathlib,yaml; yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text())"`
  -> exit 0.
- Run `python -m pytest -q` -> all tests pass.
- Run `python -m black --check tests` and `python -m flake8 tests` -> both exit
  0.

## Test plan

- All tests live in `tests/test_upstream_score_contract.py`.
- Tests are pure CPU unit tests and need no raw data, internet, model weights,
  or generated files.
- The expected baseline is five passing tests, plus any pre-existing tests if
  the repository drifted.
- Do not mock the functions being characterized.

## Done criteria

- [ ] `python -m pip install -e ".[dev]"` exits 0 in Python 3.10 or 3.11.
- [ ] `python -m pytest -q` exits 0 with at least five tests collected.
- [ ] `python -m black --check tests` exits 0.
- [ ] `python -m flake8 tests` exits 0.
- [ ] CI YAML parses and contains Python 3.10 and 3.11 jobs.
- [ ] `git diff --name-only` lists only `pyproject.toml`,
  `.github/workflows/ci.yml`, `tests/test_upstream_score_contract.py`, and the
  executor's status update in `plans/README.md`.
- [ ] `plans/README.md` marks Plan 001 `DONE`.

## STOP conditions

Stop and report rather than improvising if:

- `tests/` or a Python CI workflow has appeared and defines incompatible
  conventions since `c0ab96e`.
- The current `convert_annotation_to_syllables` or `expand_syllables` behavior
  differs from the excerpts above.
- Installing the existing project dependencies fails due to an unsupported
  platform or unavailable package. Record the exact package/error; do not
  rewrite dependency pins in this plan.
- The unit tests require model weights, GPU, audio, or network access because
  of import-time side effects. Report the import chain rather than adding broad
  mocks or changing upstream runtime code.

## Maintenance notes

- Later plans must keep ordinary tests independent of local raw data and
  checkpoints. Use `integration` only for explicitly optional environment
  tests.
- The unmapped-word characterization is not approval of silent skipping. Plan
  008 adds strict validation before calling upstream.
- Review CI runtime after the first run; installing the full PyTorch dependency
  stack may be expensive. Optimize caching in a separate DX task if needed,
  without weakening the test gate.
