# Plan 003: Create the independent Khalkha frontend foundation

> **Executor instructions**: Follow the steps in order and run each verification
> gate. The package must remain usable without importing VocalRender or loading
> a model. If a STOP condition occurs, stop and report rather than broadening
> scope. Update this plan's row in `plans/README.md` when done.
>
> **Drift check (run first)**:
> `git diff --stat c0ab96e..HEAD -- pyproject.toml src/khalkha_frontend tests`
> Confirm Plans 001 and 002 are `DONE` and the semantic resource paths exist.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: `plans/001-establish-verification-baseline.md`,
  `plans/002-normalize-layout-and-provenance.md`
- **Category**: architecture / DX
- **Planned at**: commit `c0ab96e`, 2026-08-15

## Why this matters

Khalkha text processing must not be scattered through a Chinese-oriented SVS
engine. This plan creates a reusable, neutral package with conservative text
normalization, explicit unresolved states, and injectable resource paths.
Later morphology, phonology, tokenizer, and score-adapter work can then share
one vocabulary without coupling basic language logic to PyTorch or model code.

## Current state

- `src/` currently contains only `vocalrender/`.
- `pyproject.toml:77-82` discovers packages from `src` but explicitly includes
  only `vocalrender*`:

  ```toml
  [tool.setuptools.packages.find]
  where = ["src"]
  include = ["vocalrender*"]
  ```

- Runtime dependencies already include Pydantic and PyYAML, but the foundation
  can use standard-library dataclasses and enums to stay lightweight.
- `src/vocalrender/preprocessing/text_tensor.py:62-69` passes each existing
  lyric unit directly to the tokenizer. It does not provide Mongolian Unicode
  normalization or language-aware unit types.
- The design constraint from the source prompt is:

  ```text
  khalkha_frontend
          ↓
  neutral intermediate representation
          ↓
  VocalRender adapter
  ```

- Target language is Standard Khalkha Mongolian in Cyrillic. The package name
  is exactly `khalkha_frontend`; never use `mn_ling`.
- Normalization in Milestone 0 is limited to safe operations. Number expansion,
  abbreviation expansion, transliteration, and foreign-text pronunciation are
  intentionally unresolved.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Install | `python -m pip install -e ".[dev]"` | exit 0 |
| Unit tests | `python -m pytest -q tests/test_normalize.py tests/test_frontend_types.py tests/test_resource_loading.py` | all pass |
| Full tests | `python -m pytest -q` | all pass |
| Format | `python -m black --check src/khalkha_frontend tests` | exit 0 |
| Lint | `python -m flake8 src/khalkha_frontend tests` | exit 0 |
| Import boundary | `python -c "import sys,khalkha_frontend; assert 'torch' not in sys.modules and 'vocalrender' not in sys.modules"` | exit 0 |

## Scope

**In scope:**

- `pyproject.toml`
- `src/khalkha_frontend/__init__.py`
- `src/khalkha_frontend/types.py`
- `src/khalkha_frontend/normalize.py`
- `src/khalkha_frontend/resources.py`
- `tests/test_frontend_types.py`
- `tests/test_normalize.py`
- `tests/test_resource_loading.py`

**Out of scope:**

- `src/vocalrender/**`; the adapter is Plan 008.
- Syllabification, morphology parsing, G2P, phone definitions, and allophone
  rules.
- Number/abbreviation expansion, foreign-text transliteration, or language ID.
- Any IPA value or pronunciation claim.
- Reading raw audio or loading a tokenizer/model.

## Git workflow

- Branch: `codex/003-frontend-foundation`
- Suggested commit: `feat: add Khalkha frontend foundation`.
- Do not push or open a PR unless instructed.

## Steps

### Step 1: Make `khalkha_frontend` an installable independent package

Create `src/khalkha_frontend/` and update setuptools discovery to include both
`vocalrender*` and `khalkha_frontend*`. Do not rename the distribution from
`vocalrender` in this milestone.

`__init__.py` must expose a deliberately small API: the normalization function,
the neutral result/status types, and resource-path configuration. It must not
import optional/heavy dependencies.

**Verify**:

- `python -m pip install -e ".[dev]"` -> exit 0.
- `python -c "import khalkha_frontend; print(khalkha_frontend.__name__)"` ->
  prints `khalkha_frontend`.
- `python -c "import sys,khalkha_frontend; assert 'torch' not in sys.modules and 'vocalrender' not in sys.modules"`
  -> exit 0.

### Step 2: Define neutral, uncertainty-preserving types

In `types.py`, use frozen dataclasses, enums, and immutable tuples. Define at
least:

- `ResolutionStatus`: `RESOLVED`, `RESEARCH_REQUIRED`, `OVERRIDDEN`,
  `UNSUPPORTED`;
- `TextIssueKind`: `NUMBER`, `ABBREVIATION`, `FOREIGN_SCRIPT`,
  `UNSUPPORTED_CHARACTER`;
- `TextIssue`: kind, original text, start/end character offsets, message;
- `NormalizedText`: original, normalized, issues;
- `EvidenceRef`: stable ID, source kind, citation/path, optional item ID, note;
- `PronunciationUnit`: orthographic text, optional phonemic symbols, optional
  surface phones, status, evidence refs, optional manual override;
- `FrontendResult`: normalized text, lyric/syllable units, pronunciation units,
  accumulated issues.

Enforce invariants in `__post_init__`:

- resolved phonemic/surface values require at least one `EvidenceRef`;
- `OVERRIDDEN` requires a nonempty manual override and evidence/provenance note;
- `RESEARCH_REQUIRED` may have null/empty phone fields;
- spans must be nonnegative and ordered;
- tuple fields are immutable.

Do not add guessed defaults for phonemes or phones.

**Verify**:
`python -m pytest -q tests/test_frontend_types.py` -> tests prove each invariant,
including rejection of an unsupported resolved phone with no evidence.

### Step 3: Implement conservative normalization

In `normalize.py`, implement a pure function such as:

```python
def normalize_text(text: str, *, lowercase: bool = True) -> NormalizedText:
    ...
```

Allowed transformations:

1. require `str` input;
2. Unicode NFC normalization;
3. normalize all runs of Unicode whitespace to one ASCII space and trim ends;
4. lowercase Cyrillic when `lowercase=True` using Python Unicode case handling;
5. preserve Mongolian letters `Ө ө Ү ү`, Cyrillic `Ё ё`, soft sign `Ь ь`, and
   hard sign `Ъ ъ`;
6. preserve punctuation and digits verbatim, but emit typed issues for digits,
   likely abbreviations, foreign-script spans, and unsupported control
   characters instead of expanding/dropping them.

Do not transliterate, remove punctuation, expand numbers, infer abbreviations,
or map letters to IPA. Define supported script detection narrowly enough that
Latin lyrics become a `FOREIGN_SCRIPT` issue without being destroyed.

**Verify**:
`python -m pytest -q tests/test_normalize.py` -> cases cover NFC equivalence,
whitespace, case, the six special Cyrillic letter pairs, punctuation/digit
preservation, Latin issue reporting, empty input, and idempotence.

### Step 4: Add semantic resource resolution with dependency injection

In `resources.py`, define a frozen `ResourcePaths` dataclass with:

- `root` (repository/resource root selected by the caller);
- `unimorph_khk`, `lexicon`, and `phonology` properties;
- `from_repository_root(path)` constructor;
- `validate(require_raw_data: bool = False)` returning structured missing-path
  problems rather than exiting;
- optional paths for `data/raw/speech`, `benchmark_tts`, `native_speech`,
  `native_singing`, and `music3` without requiring them in a clean clone.

Resolution rules:

- explicit caller-provided root wins;
- a default repository root may be derived from `__file__` for editable/source
  checkouts, but functions must accept injection for installed packages/tests;
- never use the process current working directory as the only source of truth;
- never recognize or fall back to marker-prefixed legacy directories;
- return `Path` objects and do not create directories from a read operation.

**Verify**:

- `python -m pytest -q tests/test_resource_loading.py` -> tests use `tmp_path`
  fixtures for complete/missing layouts, confirm CWD independence, and reject a
  tree containing only legacy marker paths.
- `rg -n "__GET__|__MAKE__|mn_ling" src/khalkha_frontend tests` -> no matches.

### Step 5: Document the public foundation API in module docstrings

Document that:

- unresolved pronunciation is a valid result;
- evidence gates resolved phone values;
- `normalize_text` preserves unresolved content;
- `ResourcePaths` locates semantic directories but does not acquire data;
- the package is independent of VocalRender.

Avoid roadmap prose and unsupported linguistic examples in code comments.

**Verify**:
`python -c "import khalkha_frontend; help(khalkha_frontend)"` -> public names
and independence contract are visible.

## Test plan

- `tests/test_frontend_types.py`: invariants, immutability, evidence gating,
  equality/serialization-friendly fields.
- `tests/test_normalize.py`: deterministic safe transformations and issue
  reporting; no pronunciation assertions.
- `tests/test_resource_loading.py`: injected paths, clean-clone behavior,
  missing-data diagnostics, absence of marker fallback.
- Use table-driven pytest parametrization for Cyrillic characters and issues.
- Do not access real raw audio or checkpoints.

## Done criteria

- [ ] Editable install exposes both `vocalrender` and `khalkha_frontend`.
- [ ] Importing `khalkha_frontend` imports neither `torch` nor `vocalrender`.
- [ ] Normalization is idempotent and preserves Mongolian-specific Cyrillic.
- [ ] Resolved phones cannot be constructed without evidence.
- [ ] Resource resolution uses only semantic paths and works outside repo CWD.
- [ ] `python -m pytest -q` passes.
- [ ] Black and flake8 checks pass for the in-scope paths.
- [ ] No `src/vocalrender/**` file changed.
- [ ] `plans/README.md` marks Plan 003 `DONE`.

## STOP conditions

Stop and report if:

- package discovery or distribution structure changed since `c0ab96e`;
- an existing `khalkha_frontend` package has appeared with conflicting public
  types;
- the desired normalization requires a linguistic choice rather than a Unicode
  operation;
- keeping imports lightweight would require changes inside VocalRender;
- a caller cannot inject resource paths without adding a new framework/global
  service locator.

## Maintenance notes

- Treat public dataclass fields/enums as a compatibility surface; downstream
  benchmark and adapter code will serialize them.
- New normalization transforms need a reversibility/meaning review and tests.
- Evidence requirements are intentional friction. Do not weaken them to make
  future G2P development easier.
