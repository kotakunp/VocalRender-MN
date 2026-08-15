# Plan 004: Add UniMorph access and orthographic-context mining

> **Executor instructions**: Implement only parsing and orthographic analysis.
> Do not infer sounds from spelling patterns. Follow all verification gates and
> stop if the live resource schema differs from the samples below. Update this
> plan's row in `plans/README.md` when done.
>
> **Drift check (run first)**:
> `git diff --stat c0ab96e..HEAD -- resources/unimorph_khk resources/lexicon src/khalkha_frontend scripts/mn tests experiments`
> Confirm Plans 002 and 003 are `DONE`.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: `plans/002-normalize-layout-and-provenance.md`,
  `plans/003-create-frontend-foundation.md`
- **Category**: direction / tooling
- **Planned at**: commit `c0ab96e`, 2026-08-15

## Why this matters

UniMorph and the frequency list can answer lexical and morphological questions
without pretending to be a pronunciation dictionary. A typed parser and a
context miner let researchers find real examples of Л, Г, Х, soft-sign, and
palatalization-relevant spelling environments, expand benchmarks reproducibly,
and inspect suffix boundaries. The output remains orthographic evidence until
native/linguistic validation establishes phonetic meaning.

## Current state

- After Plan 002, UniMorph lives in `resources/unimorph_khk/` and the frequency
  list in `resources/lexicon/most_frequent_words.csv`.
- The observed `khk` schema is tab-separated:

  ```text
  нэр    нэрийн    N;GEN;SG
  нэр    нэрд      N;DAT;SG
  ```

- The observed `khk.segmentations` schema has four tab-separated fields:

  ```text
  нэр    нэрийн    N|GEN;SG    нэр|ийн
  нэр    нэрд      N|DAT;SG    нэр|д
  ```

- `khk.derivations` exists and must be inspected before adding a parser. Its
  schema must not be assumed identical to inflections or segmentations.
- The local UniMorph README states this is morphology data, sourced from
  MorphyNet; it is not a phonetic transcription.
- The frequency CSV begins:

  ```csv
  word, frequency
  нь, 0.014768
  байна, 0.008926
  ```

- Plan 003 provides normalization, `ResourcePaths`, and neutral dataclasses.
- No `scripts/mn/` directory or experiment structure exists in the base commit.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused tests | `python -m pytest -q tests/test_morphology.py tests/test_context_mining.py tests/test_resource_loading.py` | all pass |
| Full tests | `python -m pytest -q` | all pass |
| Format | `python -m black --check src/khalkha_frontend scripts/mn tests` | exit 0 |
| Lint | `python -m flake8 src/khalkha_frontend scripts/mn tests` | exit 0 |
| CLI smoke | `python scripts/mn/mine_contexts.py --help` | exit 0; usage shown |

## Scope

**In scope:**

- `src/khalkha_frontend/morphology.py`
- `src/khalkha_frontend/context_mining.py`
- `src/khalkha_frontend/__init__.py` (export stable public APIs only)
- `scripts/mn/mine_contexts.py`
- `tests/test_morphology.py`
- `tests/test_context_mining.py`
- `tests/fixtures/` containing tiny synthetic TSV/CSV fixtures only
- `experiments/003_phonetic_benchmark/README.md`
- `experiments/003_phonetic_benchmark/config/context_mining.yaml`
- `experiments/003_phonetic_benchmark/results/.gitkeep` only if the repository
  convention requires retaining the empty output directory

**Out of scope:**

- Modifying source resource files.
- Training a morphology model or adding a database/server.
- Syllabification, G2P, phone/allophone values, or phonetic labels.
- Mining the raw speech audio; this plan mines text resources only.
- Automatically adding candidates to the canonical benchmark.
- Claims that a letter environment predicts a specific IPA sound.

## Git workflow

- Branch: `codex/004-morphology-context-mining`
- Suggested commits:
  `feat: add UniMorph Khalkha resource access` and
  `feat: add Mongolian orthographic context miner`.
- Do not push/open a PR unless instructed.

## Steps

### Step 1: Inspect and codify the three UniMorph schemas

Before coding, inspect the first, middle, and final nonblank rows of `khk`,
`khk.segmentations`, and `khk.derivations`; count column cardinalities and
malformed rows. Record actual schemas in the module docstring and test fixtures.

If `khk.derivations` has variable or undocumented columns, expose it through a
lossless raw-row iterator first and STOP before inventing semantic fields.

**Verify**: a one-off read-only script reports row counts and distinct column
counts; no resource file changes in `git diff`/hashes.

### Step 2: Implement typed, lazy morphology access

In `morphology.py`, define immutable records such as:

- `MorphAnalysis(lemma, surface, features, source_line)`;
- `Segmentation(lemma, surface, features, morphemes, source_line)`;
- an explicit `MorphologyLookup` result with `analyses`, `segmentations`, and
  `known: bool` rather than returning `None` ambiguously.

Implement a `UniMorphKhalkha` class that accepts an injected directory and:

- validates expected files with actionable errors;
- opens UTF-8 text and parses tabs strictly;
- normalizes lookup keys with Plan 003's safe normalizer;
- preserves duplicate analyses and source line numbers;
- splits feature bundles and segmentation pipes without assigning phonetic
  meaning;
- builds indices lazily on first query and does not mutate the source files;
- safely returns an empty/unknown result for out-of-vocabulary words;
- optionally exposes bounded iteration for audit/mining without loading every
  derivation semantic into memory.

Top-level helpers `analyze_word(word, resource=...)` and
`segment_morphemes(word, resource=...)` may wrap the class, but do not hide
path injection behind mutable globals.

**Verify**:
`python -m pytest -q tests/test_morphology.py` -> tests cover known inflection,
segmentation, OOV, duplicate analyses, malformed rows, normalization, and
source-file immutability.

### Step 3: Implement frequency-list access

Add a small reader (in `context_mining.py` unless a separate `lexicon.py` is
clearly cleaner) that validates `word` and `frequency` columns, parses frequency
as a finite nonnegative float, normalizes words, and yields stable records.
Reject malformed values with file/line diagnostics. Do not reinterpret the
frequency as a raw count.

**Verify**: fixture tests cover correct parsing, missing columns, invalid
numbers, and stable descending order without modifying the CSV.

### Step 4: Define orthographic context records and classifiers

Define an `OrthographicCandidate` record containing:

- word, normalized word, source (`frequency`, `unimorph_surface`, or
  `unimorph_lemma`), optional frequency/lemma/features;
- target grapheme and group (`L`, `G`, `H`, `PALATALIZATION`);
- occurrence index;
- left/right character context;
- position (`initial`, `medial`, `final`, `only`);
- orthographic pattern labels only, for example `CV`, `VC`, `VCV`,
  `preconsonantal`, `front_vowel_neighbor`, `back_vowel_neighbor`, `ng`,
  `soft_sign`, `Ci_candidate`;
- a note that pattern labels are candidate selectors, not phone predictions.

Use explicit Mongolian Cyrillic vowel/consonant character sets whose role is
only spelling classification. Put those sets in one named constant section and
test `ө`, `ү`, `ё`, `ь`, and `ъ`. If a classification depends on a disputed
linguistic category rather than literal adjacency, label it `candidate` and
document the limitation.

Support all source-prompt searches: `л+vowel`, `vowel+л`, `VлV`, `лC`, final
`л`; analogous `г` and `х` contexts; `нг`; soft sign; and potential `Ci`
contexts.

**Verify**:
`python -m pytest -q tests/test_context_mining.py` -> table-driven synthetic
examples cover every label and multiple occurrences in one word.

### Step 5: Add a deterministic mining CLI

Create `scripts/mn/mine_contexts.py` using argparse and library APIs only. It
must accept:

- `--resources-root` (default semantic `resources/`);
- one or more target groups/patterns;
- source selection (`frequency`, `unimorph`, or both);
- `--limit-per-pattern`;
- `--min-frequency`;
- deterministic `--output-json` and optional `--output-csv`;
- `--config` for the checked-in experiment YAML.

Sort deterministically by group, pattern, descending known frequency, word,
and occurrence. Deduplicate only identical source/word/occurrence records; do
not erase distinct morphological evidence. Output metadata must include schema
version, command/config, source manifest IDs, and generated timestamp or a
reproducible run ID kept outside content hashing.

The CLI must never edit `benchmarks/MN-PHON-250/manifest.yaml` automatically.

**Verify**:

- `python scripts/mn/mine_contexts.py --config experiments/003_phonetic_benchmark/config/context_mining.yaml --output-json <temporary-path>`
  -> exit 0 and valid JSON.
- Running twice with the same inputs produces equivalent candidate arrays
  after excluding the documented timestamp field.

### Step 6: Document the research boundary

In `experiments/003_phonetic_benchmark/README.md`, describe:

- inputs and their manifest IDs;
- exact reproduction command;
- output schema;
- how a human promotes candidates to the canonical benchmark;
- that orthographic patterns do not establish phonemes/allophones;
- that raw speech may later be linked as evidence but is not consumed here.

**Verify**:
`rg -n "phoneme|IPA|allophone" experiments/003_phonetic_benchmark/README.md`
-> every occurrence is a disclaimer or future evidence requirement, not a
mapping claim.

## Test plan

- Use tiny fixtures for error and boundary tests; one integration test may read
  the real small UniMorph/lexicon resources when present, but must skip with a
  clear reason in a clean clone without vendored resources.
- Verify exact structures for the known `нэр -> нэрийн` segmentation only as a
  morphology fact from the local file.
- Verify no output field is named `expected_phone` or contains an IPA value.
- Test deterministic ordering and nonmutation by hashing fixtures before/after.

## Done criteria

- [ ] UniMorph queries distinguish known/OOV without exceptions for ordinary
  misses.
- [ ] Segmentations preserve morpheme boundaries exactly as provided.
- [ ] Every requested spelling context can be mined deterministically.
- [ ] Candidate outputs contain provenance and no phonetic claims.
- [ ] CLI never edits canonical benchmark/resource inputs.
- [ ] `python -m pytest -q` passes.
- [ ] Black and flake8 checks pass.
- [ ] No source file under `src/vocalrender/` changed.
- [ ] `plans/README.md` marks Plan 004 `DONE`.

## STOP conditions

Stop and report if:

- UniMorph column shapes differ materially from the observed schemas;
- derivation semantics cannot be established from the resource itself;
- the lexical frequency list lacks source/license provenance and an executor is
  about to commit/relicense it rather than merely read the existing local file;
- a requested pattern requires assigning an unverified phonetic interpretation;
- memory use would require a new storage service or broad dependency.

## Maintenance notes

- UniMorph revisions may change rows and licenses; update manifest revision and
  parser tests together.
- Context classifiers are benchmark-candidate tooling, not language rules.
- Reviewers should reject any future PR that converts a spelling pattern into a
  phone without evidence and benchmark/native validation.
