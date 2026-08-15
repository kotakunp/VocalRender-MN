# Plan 002: Normalize permanent data/resource paths and record provenance

> **Executor instructions**: This plan moves user-supplied files. Resolve and
> print every source/destination first, perform collision checks, and never
> delete a source until the destination is verified. Run every verification
> gate. If a STOP condition occurs, stop and report; do not merge directories
> heuristically. Update this plan's row in `plans/README.md` when done.
>
> **Drift check (run first)**:
> `git diff --stat c0ab96e..HEAD -- .gitignore DATA_SOURCES.md resources data/raw benchmarks tests`
> Also run `git status --short` because the relevant resources were untracked at
> planning time. Any unexpected tracked or untracked destination is a STOP
> condition until reconciled.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: `plans/001-establish-verification-baseline.md`
- **Category**: migration / docs
- **Planned at**: commit `c0ab96e`, 2026-08-15

## Why this matters

The current `__GET__` and `__MAKE__` names encode how the initial workspace was
assembled, not what the resources are. Keeping them in permanent APIs would
leak setup history throughout code and experiments. Move to semantic paths,
preserve all local data, and record provenance/licensing explicitly so future
training decisions do not confuse availability with permission.

## Current state

The following paths existed on 2026-08-15:

| Current path | Observed contents | Permanent path |
|---|---|---|
| `resources/__GET__unimorph_khk/` | `khk`, `khk.segmentations`, `khk.derivations`, `README.md` (~3.4 MB) | `resources/unimorph_khk/` |
| `resources/__GET__mongolian_lexicon/` | `most_frequent_words.csv` (columns `word, frequency`) | `resources/lexicon/` |
| `resources/__MAKE__phoneme_inventory/` | empty | merge concept into `resources/phonology/` |
| `resources/__MAKE__pronunciation_lexicon/` | empty | merge concept into `resources/phonology/` or `resources/lexicon/` by artifact type |
| `data/raw/__GET__speech/` | `mbspeech/` plus `spoken_words/` (42,397 Opus clips and metadata) | `data/raw/speech/` |
| `benchmarks/__MAKE__MN-PHON-250/` | `manifest.yaml`; empty `results/` | `benchmarks/MN-PHON-250/` |

Other relevant facts:

- `pretrained_models/VocalRender-Pro/` is already semantically named and must
  not move.
- `.gitignore:10-18` ignores the entire `data/` tree and all pretrained models.
- `.gitignore:20-24` ignores common audio extensions. These protections must
  remain.
- UniMorph's local `README.md` attributes `khk` and segmentations to MorphyNet
  and states CC BY-SA 3.0. Do not infer the licenses of the frequency list,
  MBSpeech, Spoken Words/Common Voice derivatives, or generated Music3 output
  from that statement.
- `data/raw/speech/mbspeech/` currently contains 90 pipe-delimited transcript
  CSVs. No audio files were observed there, so its purpose must be recorded as
  transcript/reference-only until proven otherwise.
- `data/raw/speech/spoken_words/` contains Common Voice-derived word clips,
  forced-alignment metadata, and split CSVs. Preserve its nested layout.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Status | `git status --short` | user changes visible; no cleanup performed |
| Tests | `python -m pytest -q` | exit 0 |
| Layout test | `python -m pytest -q tests/test_data_layout.py` | all pass |
| Format | `python -m black --check tests` | exit 0 |
| Lint | `python -m flake8 tests` | exit 0 |
| Marker scan | `git ls-files | grep -E '__(GET|MAKE)__'` | no output (use `rg` equivalent on Windows) |

For the marker scan on PowerShell use:
`git ls-files | Select-String -Pattern '__(GET|MAKE)__'`; success means no
matches. Also scan the filesystem directories explicitly after migration with
`Get-ChildItem -Directory -Recurse | Where-Object Name -Match '^__(GET|MAKE)__'`.

## Scope

**In scope:**

- `.gitignore`
- `DATA_SOURCES.md` (create)
- `resources/manifest.yaml` (create)
- `data/raw/manifest.yaml` (create and deliberately re-include in git)
- `resources/unimorph_khk/` (move intact)
- `resources/lexicon/` (move intact)
- `resources/phonology/` (create; preserve any late-arriving files from both
  former `__MAKE__` directories without collisions)
- `data/raw/speech/` (local move intact)
- `data/raw/benchmark_tts/`, `data/raw/native_speech/`,
  `data/raw/native_singing/`, `data/raw/music3/` (create locally)
- `benchmarks/MN-PHON-250/` (move intact)
- `tests/test_data_layout.py` (create)

**Out of scope:**

- Editing the contents of the benchmark manifest (Plan 005).
- Parsing UniMorph or speech metadata (Plan 004).
- Downloading, deleting, recompressing, renaming individual corpus files, or
  generating checksums for tens of thousands of raw audio clips.
- Committing any raw audio or pretrained weight.
- Making a final claim that a resource is training-eligible when its terms are
  not locally verified.

## Git workflow

- Branch: `codex/002-normalize-data-layout`
- Prefer two commits: `chore: normalize Mongolian resource layout`, then
  `docs: record Mongolian data provenance`.
- Do not push or open a PR unless instructed.

## Steps

### Step 1: Inventory and collision-check every move

Print canonical absolute source and destination paths. For each mapping:

1. assert the source is within the repository;
2. count files and total bytes;
3. record relative file paths and SHA-256 for small resource/benchmark files;
4. assert the destination does not exist, or if it exists, STOP and report its
   contents rather than merging;
5. record the counts in the execution notes before moving.

For the large speech tree, file count and total bytes are sufficient before
and after; do not hash every audio file. The observed speech inventory is a
sanity check, not a required exact value if the user added files after planning.

**Verify**: source paths resolve inside the repository and every destination is
either absent or explicitly approved by the operator.

### Step 2: Move to semantic permanent paths

Perform same-volume directory renames/moves for UniMorph, lexicon, speech, and
the benchmark. Do not copy-then-delete unless a same-volume rename is
impossible. Create the remaining semantic directories.

For the two empty `resources/__MAKE__*` directories:

- if still empty, create `resources/phonology/` and remove only the empty marker
  directories after confirming zero files;
- if either gained files, classify each file by meaning and STOP with a proposed
  mapping. Do not silently coalesce or overwrite.

After the moves, compare file counts and total byte counts with Step 1. Keep the
original relative layout beneath `data/raw/speech/`.

**Verify**:

- all permanent paths in `plans/README.md` exist locally;
- moved nonempty trees have identical file counts and byte totals;
- no `__GET__` or `__MAKE__` directory remains;
- `pretrained_models/VocalRender-Pro/` is untouched.

### Step 3: Make provenance manifests canonical

Create `resources/manifest.yaml` and `data/raw/manifest.yaml`. Use a versioned
schema with a top-level `schema_version: 1` and a list of resources. Every
entry must include:

```yaml
id: stable_snake_case_id
name: human-readable name
local_path: repository-relative semantic path
source_url: null-or-url
upstream_repository: null-or-url
version_or_revision: null-or-string
acquired_on: null-or-ISO-date
license:
  identifier: null-or-SPDX-like-string
  source: null-or-url-or-local-file
redistribution: allowed | prohibited | unknown
training_use: allowed | prohibited | unknown
research_evaluation_use: allowed | prohibited | unknown
contains_personal_data: true | false | unknown
checksums: []
notes: ""
```

Rules:

- Record unknown terms as `unknown`; never guess.
- For UniMorph, cite its local README and record the stated CC BY-SA 3.0, while
  noting that downstream redistribution must preserve attribution/share-alike.
- Record the lexicon CSV as a distinct resource with unknown license until its
  source is verified.
- Record `mbspeech` and `spoken_words` separately even though both live under
  `data/raw/speech/`.
- Add placeholder entries for native speech, benchmark TTS, native singing,
  and Music3 only as local collection/output categories. Do not fabricate a
  provider, license, or terms.
- Small vendored text resources may list SHA-256 checksums. Raw audio collections
  should instead record dataset version files and aggregate counts.
- Paths in manifests must use forward slashes and never contain markers.

**Verify**:
`python -c "import pathlib,yaml; [yaml.safe_load(pathlib.Path(p).read_text(encoding='utf-8')) for p in ('resources/manifest.yaml','data/raw/manifest.yaml')]"`
-> exit 0.

### Step 4: Write the human-readable provenance policy

Create `DATA_SOURCES.md` with:

- the difference among Apache-2.0 code, dataset licenses, and generated-output
  service terms;
- a table linking every manifest entry to its local path and intended current
  use;
- a clear statement that ordinary speech is research/reference material in
  Milestone 0 and is not VocalRender training input;
- redistribution and training-use status with `unknown` shown prominently;
- instructions to update both the manifest and this document when acquiring,
  removing, or changing a resource;
- a policy that source URLs and license evidence, not directory prefixes,
  encode provenance;
- a warning not to commit raw audio/checkpoints.

Do not reproduce personal identifiers from speech metadata.

**Verify**:
`rg -n "__GET__|__MAKE__" DATA_SOURCES.md resources/manifest.yaml data/raw/manifest.yaml`
-> no matches.

### Step 5: Rework ignore rules so metadata is tracked and payloads stay local

Replace the broad `data/` ignore with ordered rules that:

- ignore everything under `data/` by default;
- re-include `data/raw/` itself and `data/raw/manifest.yaml`;
- continue to ignore all raw-data child directories and audio payloads;
- do not re-include checkpoint or generated audio paths.

Use `git check-ignore -v` on:

- `data/raw/manifest.yaml` -> must report **not ignored**;
- one existing `.opus` under `data/raw/speech/` -> must report ignored;
- `pretrained_models/VocalRender-Pro/model.safetensors` -> must report ignored.

Do not force-add ignored audio.

**Verify**: the three `git check-ignore` expectations above hold.

### Step 6: Add layout/provenance tests

Create `tests/test_data_layout.py` using pathlib and PyYAML. Tests must:

1. load both manifests and assert `schema_version == 1`;
2. reject marker strings in all `local_path` values;
3. require unique resource IDs and local paths;
4. require every listed resource to have explicit license/use status fields,
   even when the value is `unknown`;
5. assert semantic resource directories exist;
6. treat the four future audio-source directories as optional/empty at test
   time if the whole ignored data payload is absent in CI;
7. assert committed paths from `git ls-files` contain no marker directories;
8. ensure no audio/checkpoint extension is accidentally tracked outside the
   existing explicit demo exceptions.

Tests must work in a clean clone where ignored raw data is absent.

**Verify**:

- `python -m pytest -q tests/test_data_layout.py` -> all pass locally and with
  raw data temporarily unavailable.
- `python -m pytest -q` -> full suite passes.
- `python -m black --check tests` and `python -m flake8 tests` -> exit 0.

## Test plan

- Primary test file: `tests/test_data_layout.py`.
- Use repository-root fixtures derived from `Path(__file__).resolve()`; never
  depend on the current working directory.
- Parse the real small manifests but do not enumerate the full speech corpus in
  ordinary unit tests.
- Use a subprocess call to `git ls-files` only for the tracked-file safety test;
  skip with an explicit reason if `.git` is unavailable in a source archive.

## Done criteria

- [ ] All permanent target directories exist locally and no directory name
  begins with `__GET__` or `__MAKE__`.
- [ ] Moved trees have the same file counts and byte totals as before the move.
- [ ] `resources/manifest.yaml`, `data/raw/manifest.yaml`, and
  `DATA_SOURCES.md` contain no marker paths and parse successfully.
- [ ] Unknown licenses/use rights remain explicitly `unknown`.
- [ ] `git check-ignore` proves raw audio/checkpoints remain ignored while the
  data manifest is trackable.
- [ ] `git status --short` shows no raw audio payload staged.
- [ ] `python -m pytest -q` passes.
- [ ] No source file under `src/vocalrender/` changed.
- [ ] `plans/README.md` marks Plan 002 `DONE`.

## STOP conditions

Stop and report if:

- any destination already exists or a source disappeared since recon;
- before/after counts or byte totals differ;
- a former empty `__MAKE__` directory now contains user files;
- a move would cross volumes and require deleting the source after copy without
  an independently verified checksum/count;
- license terms conflict across local metadata or remain ambiguous enough that
  an entry would be labeled `allowed` only by assumption;
- ignore-rule changes make any raw audio or model weight trackable;
- implementing the migration appears to require deleting, resetting, or
  cleaning unrelated user work.

## Maintenance notes

- Any new external asset gets a semantic path plus manifest entry; marker
  prefixes are never reintroduced.
- Reviewers should scrutinize staged files by size and extension before commit.
- Data manifests describe rights/evidence as currently known; they are not
  legal advice and must be updated when upstream terms change.
- Plan 005 owns changes to benchmark content. This plan only moves it intact.
