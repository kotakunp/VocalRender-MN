# Plan 005: Canonicalize MN-PHON-250 and its manual evaluation metadata

> **Executor instructions**: Preserve all 250 existing items and their text.
> Convert the draft into a versioned, item-oriented schema without filling any
> expected phoneme/phone from memory or from unsourced comments. Run each gate
> and stop on drift or ambiguity. Update this plan's row in
> `plans/README.md` when done.
>
> **Drift check (run first)**:
> `git diff --stat c0ab96e..HEAD -- benchmarks/MN-PHON-250 src/khalkha_frontend scripts/mn tests data/raw/manifest.yaml`
> Confirm Plans 002 and 003 are `DONE` and inspect the live draft before
> conversion.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: `plans/002-normalize-layout-and-provenance.md`,
  `plans/003-create-frontend-foundation.md`
- **Category**: tests / research tooling
- **Planned at**: commit `c0ab96e`, 2026-08-15

## Why this matters

The current benchmark is a useful 250-item candidate list but cannot store
item-level evidence, audio takes, or manual ratings. It also contains IPA-like
section comments that are hypotheses rather than sourced conclusions. A
canonical manifest must preserve the expanded user work, make uncertainty
machine-checkable, and support native speech, native singing, benchmark TTS,
and Music3 comparisons without requiring any audio to exist yet.

## Current state

- Plan 002 moves the draft to
  `benchmarks/MN-PHON-250/manifest.yaml` without altering it.
- The draft metadata says:

  ```yaml
  benchmark:
    name: MN-SVS Targeted Phonetic Benchmark
    version: "1.0"
    dialect_target: "Standard Khalkha Mongolian"
    item_count: 250
  ```

- Items are nested under section/group names and three-digit numeric keys, for
  example:

  ```yaml
  sections:
    L:
      carrier_CV:
        001: ла
        002: лэ
  ```

- The four top-level groups are `L`, `G`, `H`, and `PALATALIZATION`; numeric
  keys run through 250.
- `benchmarks/__MAKE__MN-PHON-250/manifest.yaml:10-12`, `:95-97`, and
  `:194-196` contained unsourced IPA-like labels in comments. Treat these only
  as research hypotheses; do not copy them into `expected_phoneme` or
  `expected_phone`.
- The earlier source prompt described MN-PHON-130, but the actual workspace has
  a newer 250-item draft. Preserve the actual 250-item set and name.
- Planned semantic audio roots are:

  ```text
  data/raw/native_speech/MN-PHON-250/
  data/raw/benchmark_tts/MN-PHON-250/
  data/raw/music3/MN-PHON-250/
  data/raw/native_singing/phonetic/
  ```

- Audio folders may be absent/empty in CI. Validation must not require payloads
  unless explicitly run with a strict file-check flag.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Validate | `python scripts/mn/validate_benchmark.py benchmarks/MN-PHON-250/manifest.yaml` | exit 0; reports 250 valid items |
| Tests | `python -m pytest -q tests/test_benchmark_manifest.py` | all pass |
| Full tests | `python -m pytest -q` | all pass |
| Format | `python -m black --check src/khalkha_frontend scripts/mn tests` | exit 0 |
| Lint | `python -m flake8 src/khalkha_frontend scripts/mn tests` | exit 0 |
| Marker scan | `rg -n "__GET__|__MAKE__|MN-PHON-130" benchmarks/MN-PHON-250 src/khalkha_frontend scripts/mn tests` | no active-path matches |

## Scope

**In scope:**

- `benchmarks/MN-PHON-250/manifest.yaml` (schema migration preserving items)
- `benchmarks/MN-PHON-250/audio_manifest.yaml` (create)
- `benchmarks/MN-PHON-250/evaluations.yaml` (create)
- `benchmarks/MN-PHON-250/README.md` (create)
- `src/khalkha_frontend/benchmark.py` (create)
- `src/khalkha_frontend/__init__.py` (export stable benchmark types/loaders)
- `scripts/mn/validate_benchmark.py` (create)
- `tests/test_benchmark_manifest.py` (create)
- `tests/fixtures/benchmark/` with tiny valid/invalid manifests
- `data/raw/manifest.yaml` only if Plan 002 placeholder paths must be updated
  from MN-PHON-130 to MN-PHON-250

**Out of scope:**

- Creating/generating audio, calling TTS or Music3, or collecting recordings.
- Assigning expected phonemes/phones without evidence.
- Automatic acoustic scoring or deciding GREEN/YELLOW/RED from a single rating.
- Changing item spellings, removing apparent duplicates, or adding new items.
- Syllabification/G2P implementation.

## Git workflow

- Branch: `codex/005-canonicalize-mn-phon-250`
- Suggested commits:
  `data: canonicalize MN-PHON-250 manifest` and
  `test: validate phonetic benchmark metadata`.
- Do not push/open a PR unless instructed.

## Steps

### Step 1: Snapshot and audit the legacy draft before conversion

Write a temporary read-only conversion/audit script or test helper that parses
the live nested YAML and emits:

- group/category/key/text for every item;
- total count and numeric key range;
- duplicate numeric keys, duplicate text strings, gaps, empty values;
- SHA-256 of the original file.

Store the original hash and a generated mapping table in execution notes, not
as a second canonical manifest. Duplicate text may be intentional across
contexts; report it but do not remove it.

**Verify**: exactly 250 entries and keys 001-250 are accounted for. If not,
STOP before rewriting.

### Step 2: Define versioned benchmark library types and invariants

In `benchmark.py`, use immutable dataclasses/enums plus explicit validators.
Define at least:

- `Lexicality`: `carrier`, `lexical`, `contrast` (allow an explicit
  `unknown` only for migration edge cases);
- `EvaluationStatus`: `untested`, `in_progress`, `evaluated`, `needs_review`;
- `AudioSource`: `native_speech`, `native_singing`, `benchmark_tts`, `music3`;
- `BenchmarkItem` with ID, text, target grapheme/group, lexicality, context,
  position, left/right context, expected phoneme/phone, evidence refs, and
  notes;
- `AudioTake` with item ID, source, run/take ID, repository-relative path,
  provider/speaker pseudonym, prompt/config provenance, checksum, and notes;
- `ManualRating` with item ID, audio take ID, score (0/1/2), rater pseudonym,
  timestamp, confidence, notes;
- aggregate/traffic-light output as a derived view, never primary truth.

Invariants:

- IDs match `MNPHON_001` through `MNPHON_250` and are unique;
- item count metadata equals actual item count;
- `expected_phoneme` or `expected_phone` may be non-null only with at least one
  evidence ref whose source is linguistic literature, native speech/singing,
  or native-speaker validation;
- item text is nonempty NFC-normalized text;
- audio paths are relative, use forward slashes, live beneath one of the four
  semantic raw roots, and contain no marker segments or `..`;
- rating scores are integers in `{0,1,2}`;
- every rating references a declared audio take and every take references a
  declared item;
- missing audio files are warnings by default and errors only under an explicit
  strict file-check mode.

Do not depend on a Pydantic-version-specific feature when dataclasses plus
manual validation suffice.

**Verify**:
`python -m pytest -q tests/test_benchmark_manifest.py -k schema` -> valid
fixtures load and each invalid invariant is rejected with item/file context.

### Step 3: Convert the 250 nested items to canonical item records

Set `schema_version: 2`, retain benchmark name/dialect, and use a top-level
ordered `items` list. Convert numeric key `001` to `MNPHON_001` and preserve the
exact text. Derive only transparent orthographic metadata from legacy group and
category names:

- `target_group`: `L`, `G`, `H`, or `PALATALIZATION`;
- `legacy_category`: exact former nested category;
- `lexicality`: from explicit category prefixes (`carrier_`, `lexical_`,
  `minimal_contrast_`), with no phonetic inference;
- `context`/`position` only when the legacy name directly encodes it;
- `target_grapheme`: literal `л`, `г`, `х`, or relevant soft-sign/contrast
  marker when unambiguous; otherwise null plus a migration note;
- `left_context`/`right_context`: literal adjacent characters when the target
  occurrence is unambiguous; otherwise null rather than guessing;
- `expected_phoneme: null`, `expected_phone: null`, `evidence: []`,
  `status: untested`, `notes: ""` for every item unless the repository contains
  explicit sourced evidence added after planning.

Move former IPA comments to a benchmark-level `research_hypotheses` section
worded as questions and linked to no expected field, or omit them. Do not state
the phones as facts.

**Verify**:

- the validator reports `250 valid items`;
- a conversion comparison proves every legacy `(number, text, group,
  category)` appears exactly once in the new manifest;
- `expected_phoneme` and `expected_phone` are null for all 250 entries unless a
  reviewer can trace a non-null entry to an explicit evidence record.

### Step 4: Create audio-take and evaluation manifests

Create separate, versioned `audio_manifest.yaml` and `evaluations.yaml` so
repeated generations/ratings do not bloat or churn the item definition file.
Initially they may contain empty lists plus documented examples in comments or
README. Do not create fake take/rating records.

Use stable take IDs such as `MNPHON_001_music3_a` only when a file actually
exists or an acquisition record is created. Allow three Music3 runs (`a`, `b`,
`c`) without hard-coding that every item must have all three.

Traffic-light derivation rules must be explicit and conservative. Recommended
initial policy:

- no ratings -> `UNTESTED`;
- all available independent ratings are 2 and minimum configured count met ->
  `GREEN`;
- any 0 or mixed results -> `RED`/`YELLOW` only according to a documented
  aggregate policy;
- do not compute a color if rater independence/minimum count is not met.

If the policy cannot be agreed from repository intent, implement ratings only
and defer color derivation rather than inventing thresholds.

**Verify**: empty manifests validate; fixtures prove referential integrity and
score constraints without requiring files.

### Step 5: Add the validator CLI

Create `scripts/mn/validate_benchmark.py` with:

- positional benchmark manifest;
- optional `--audio-manifest` and `--evaluations` defaulting to sibling files;
- `--strict-files` to require referenced audio payloads;
- `--json-report` for a machine-readable report;
- nonzero exit on schema/invariant errors, zero on warnings;
- summary counts by group/category/status/source and unresolved expected fields.

It must not modify manifests or audio.

**Verify**:

- default command exits 0 and reports 250 valid items with empty/missing audio
  payload warnings only;
- an invalid fixture exits nonzero and names the failing item/field;
- `--strict-files` exits nonzero when a fixture references a missing file.

### Step 6: Document collection and annotation workflow

Write `benchmarks/MN-PHON-250/README.md` covering:

- goal and limitations;
- Standard Khalkha/Cyrillic target;
- four audio source roles, with native speech primary and native singing as
  later singing ground truth;
- directory conventions using only semantic paths;
- manual 2/1/0 meanings;
- how to add evidence before resolving expected fields;
- how to add a take and rating without exposing personal data;
- exact validation commands;
- statement that ordinary speech is reference material, not direct SVS
  training data in Milestone 0;
- statement that Music3 is a pronunciation research/teacher candidate, not the
  final score-controlled inference engine.

**Verify**:
`rg -n "__GET__|__MAKE__|MN-PHON-130" benchmarks/MN-PHON-250` -> no matches.

## Test plan

- `tests/test_benchmark_manifest.py` loads the real canonical manifest and
  asserts 250 contiguous unique IDs.
- Fixture cases: duplicate ID, wrong count, missing required field, non-NFC
  text, non-null phone without evidence, path traversal, marker path, invalid
  score, dangling take/rating reference, missing file warning vs strict error.
- Add a legacy-conversion preservation test until migration is reviewed; it may
  use a frozen mapping fixture rather than retaining the full old manifest.
- Do not assert any guessed syllabification or IPA value.

## Done criteria

- [ ] All 250 legacy item numbers/texts/groups/categories are preserved exactly
  once in the v2 manifest.
- [ ] Every resolved expected phoneme/phone, if any, has explicit evidence;
  otherwise fields are null.
- [ ] Empty audio/evaluation manifests validate without payload files.
- [ ] Default validator reports 250 valid items and exits 0.
- [ ] Strict missing-file mode behaves as documented.
- [ ] No active benchmark path contains `__GET__`, `__MAKE__`, or MN-PHON-130.
- [ ] `python -m pytest -q` passes; Black and flake8 pass.
- [ ] No source file under `src/vocalrender/` changed.
- [ ] `plans/README.md` marks Plan 005 `DONE`.

## STOP conditions

Stop and report if:

- the live draft does not contain exactly 250 accounted-for items;
- any item text/key/group would be lost or ambiguously mapped;
- existing non-null phonetic values lack traceable evidence;
- the operator has a newer benchmark name/version not reflected in the live
  repository;
- path validation would require committing or moving raw audio;
- implementing traffic-light summaries requires thresholds not established by
  project intent.

## Maintenance notes

- Item definitions, audio takes, and human judgments are separated to minimize
  merge conflicts and preserve auditability.
- Never edit an item ID after audio/ratings reference it; add deprecation or
  supersession metadata instead.
- Reviewer focus: preservation mapping, evidence gating, path traversal checks,
  and no fabricated phonology.
