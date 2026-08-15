# Plan 008: Add a score-preserving VocalRender adapter

> **Executor instructions**: Preserve explicit note control and fail closed on
> ambiguous lyric-note alignment. Do not modify upstream VocalRender internals
> or claim it consumes explicit phones before that pathway exists. Follow every
> verification gate and update this plan's row in `plans/README.md` when done.
>
> **Drift check (run first)**:
> `git diff --stat c0ab96e..HEAD -- src/khalkha_frontend src/vocalrender scripts/mn tests examples`
> Confirm Plans 003 and 006 are `DONE` and re-read the live upstream score
> helpers before implementation.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: `plans/003-create-frontend-foundation.md`,
  `plans/006-scaffold-evidence-gated-phonology.md`
- **Category**: architecture / correctness
- **Planned at**: commit `c0ab96e`, 2026-08-15

## Why this matters

VocalRender already accepts score-native lyric units with exact pitches, note
values, tempo, and melisma mapping. The Khalkha frontend needs a narrow adapter
that validates and serializes this contract without guessing how words split or
which syllable belongs to which note. Keeping pronunciation metadata alongside
the score—but outside the current upstream prompt—allows raw, explicit-phone,
and hybrid experiments without sacrificing deterministic score control.

## Current state

- Upstream required score fields are `word`, `pitch`, `note`, `pitch2word`, and
  `bpm`; optional `word_dur`/`pitch_dur` are visualization/evaluation metadata.
- `src/vocalrender/preprocessing/svs_prompt.py:36-52` reconstructs prompts:

  ```python
  words = list(sample.get("word", []))
  bpm = int(sample.get("bpm", 120))
  pitches = [int(p) for p in sample["pitch"]]
  notes = [str(n) for n in sample["note"]]
  pitch2word = [int(p) for p in sample.get("pitch2word", list(range(len(pitches))))]
  syllables = convert_annotation_to_syllables(words, pitches, notes, pitch2word)
  ```

- `src/vocalrender/training/svs_raw_data.py:57-91` skips a lyric unit with no
  pitch mapping and represents melisma as multiple pitch/note entries under one
  word.
- `src/vocalrender/preprocessing/text_tensor.py:83-87` silently defaults an
  unknown note token to quarter note. The adapter must reject invalid note
  tokens before upstream reaches this fallback.
- `src/vocalrender/model/svs_utils.py` is the canonical source of supported
  pitch/note/BPM token maps; do not duplicate magic token lists if the adapter
  can query a lightweight helper without loading the model.
- Plan 006 keeps explicit phonemic/surface overrides as neutral evidence-backed
  metadata. The released VocalRender prompt path currently tokenizes `word`
  strings; there is no validated explicit-phone conditioning channel.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused tests | `python -m pytest -q tests/test_vocalrender_adapter.py` | all pass |
| CLI help | `python scripts/mn/prepare_score.py --help` | exit 0 |
| Example conversion | `python scripts/mn/prepare_score.py examples/mn_score_input.json --output <temporary-json>` | exit 0; valid upstream JSON emitted |
| Full tests | `python -m pytest -q` | all pass |
| Format/lint | `python -m black --check src/khalkha_frontend scripts/mn tests` then `python -m flake8 src/khalkha_frontend scripts/mn tests` | both exit 0 |

## Scope

**In scope:**

- `src/khalkha_frontend/vocalrender_adapter.py`
- `src/khalkha_frontend/types.py` only for additive score types/invariants
- `src/khalkha_frontend/__init__.py` for adapter exports
- `scripts/mn/prepare_score.py`
- `tests/test_vocalrender_adapter.py`
- `tests/fixtures/scores/` with small synthetic/Mongolian score JSON fixtures
- `examples/mn_score_input.json`
- `examples/mn_vocalrender_score.json`
- a short Mongolian adapter section in `README.md` only if it does not displace
  upstream documentation

**Out of scope:**

- Editing any file under `src/vocalrender/`.
- Changing the tokenizer, score token definitions, inference script, model, or
  training format.
- Automatic MIDI parsing or piano-roll GUI.
- Guessing syllabification/alignment from a full sentence when the caller did
  not provide it.
- Sending explicit phones into VocalRender as if supported; preserve them only
  in sidecar metadata for future experiments.
- Running full GPU inference (Plan 009).

## Git workflow

- Branch: `main` (work directly; do not create a task branch)
- Suggested commit: `feat: add score-preserving Khalkha VocalRender adapter`.
- Do not push/open a PR unless instructed.

## Steps

### Step 1: Define a strict neutral score contract

Add immutable types such as:

- `ScoreNote(midi_pitch, note_value)`;
- `LyricScoreUnit(text, notes, pronunciation=None, source_span=None)`;
- `KhalkhaScore(units, bpm, item_name, prompt_audio=None, metadata={})`;
- `VocalRenderScoreEntry` mirroring only the upstream JSON fields plus a
  namespaced `mn_frontend` sidecar that upstream can ignore.

Invariants:

- at least one lyric unit and one note;
- every lyric unit has one or more notes, so no upstream silent skip;
- MIDI pitch is an integer 0-127, with 0 reserved for explicit rest/silence
  units according to upstream semantics;
- note value is present in the supported token map;
- BPM is an integer represented by the upstream BPM token range;
- text is nonempty normalized lyric text or an explicitly permitted upstream
  silence marker;
- `item_name` is nonempty and safe as metadata, not used as a file path;
- pronunciation overrides obey Plan 006 evidence rules.

Do not add defaults that conceal missing score information.

**Verify**:
focused tests cover every validation boundary and prove types are immutable.

### Step 2: Implement deterministic flattening to the upstream schema

`to_vocalrender_entry(score)` must:

- emit one `word` element per explicit lyric/syllable unit in order;
- flatten each unit's notes into `pitch` and `note` arrays;
- emit the source unit index into `pitch2word` for every flattened note;
- copy one global BPM;
- preserve `item_name`;
- omit `word_dur`/`pitch_dur` unless supplied as verified metadata;
- put normalization issues, unresolved pronunciation, evidence IDs, and manual
  overrides under a namespaced sidecar such as `mn_frontend`, without changing
  `word` text or pretending upstream consumes phones.

Example required shape for one melisma:

```json
{
  "word": ["би", "хайр"],
  "pitch": [60, 64, 67],
  "note": ["<NOTE_8>", "<NOTE_8>", "<NOTE_4>"],
  "pitch2word": [0, 1, 1],
  "bpm": 96
}
```

Validate the emitted structure before returning. Do not rely on upstream
fallbacks for malformed arrays.

**Verify**:
tests assert exact dictionaries for one-to-one notes, melisma, repeated lyric
text, rests, and pronunciation sidecar data.

### Step 3: Add reverse validation for existing upstream entries

Provide `validate_vocalrender_entry(entry)` and optionally a lossless
`from_vocalrender_entry` for the supported subset. Validate:

- equal `pitch`/`note`/`pitch2word` lengths;
- each mapping index is in `word` range and mapping order is nondecreasing if
  that is required by the live upstream behavior;
- every word index is referenced at least once unless it is a recognized
  silence/non-lyric marker intentionally exempted;
- supported note/BPM/pitch values;
- no implicit character splitting of multi-character Mongolian units;
- sidecar schema is optional and ignored by upstream fields.

Characterize any ambiguous upstream behavior in tests; do not change upstream.

**Verify**:
invalid fixtures fail with field/index-specific errors before prompt building.

### Step 4: Create a conversion CLI

`scripts/mn/prepare_score.py` accepts a neutral JSON input with explicit lyric
units and their note arrays, then:

1. normalizes unit text via the frontend;
2. preserves/issues unresolved pronunciation diagnostics;
3. validates explicit alignment;
4. emits a JSON array consumable by
   `scripts/infer_vocalrender_svs_single.py`;
5. supports `--output -` for stdout and refuses to overwrite an existing file
   unless `--force` is explicit;
6. never runs inference or loads a checkpoint.

If the input provides full text but no unit/note alignment, return a clear
nonzero error instructing the caller to provide units or an evidence-backed
syllabification—not a guessed split.

**Verify**:
example conversion exits 0; emitted JSON passes adapter validation and has the
expected `pitch2word` melisma mapping.

### Step 5: Add stable examples and documentation

Create paired example files using a small Standard Khalkha Cyrillic score with
explicit units. The neutral input demonstrates multiple notes for one unit; the
output demonstrates upstream fields and `mn_frontend` diagnostics. Do not add
expected IPA/phones.

Document that:

- score control is authoritative;
- the adapter does not infer note timing/alignment;
- raw text remains the baseline payload to the released checkpoint;
- explicit phone overrides are preserved for future experimental adapters but
  are not consumed by current VocalRender inference;
- prompt singer audio is still required by the released checkpoint.

**Verify**:
round-trip validation and all focused/full tests pass.

## Test plan

- Exact-shape unit tests for one note per unit, melisma, repeated text, and
  rests.
- Validation errors for missing mappings, array mismatch, out-of-range MIDI/BPM,
  unsupported note token, descending/invalid mapping, unreferenced lyric unit,
  empty text, and unsupported implicit alignment.
- A regression test passes adapter output to
  `convert_annotation_to_syllables`/`expand_syllables` and proves word indices
  and melisma survive. Do not require tokenizer/model.
- Test neutral examples parse and match the checked-in expected output.

## Done criteria

- [ ] Every emitted lyric unit maps to at least one explicit note.
- [ ] Melisma is represented solely by repeated `pitch2word` indices and
  survives upstream conversion.
- [ ] Invalid note/pitch/BPM/mapping inputs fail before upstream defaults.
- [ ] Current upstream receives raw lyric units only; phones stay namespaced
  sidecar metadata.
- [ ] No `src/vocalrender/**`, tokenizer, or checkpoint file changed.
- [ ] CLI and example conversion succeed; `python -m pytest -q` passes.
- [ ] Black and flake8 pass.
- [ ] `plans/README.md` marks Plan 008 `DONE`.

## STOP conditions

Stop and report if:

- live upstream token maps or score semantics differ from the current excerpts;
- a requested conversion lacks explicit lyric-unit-to-note alignment;
- supporting an explicit phone channel requires upstream/model/tokenizer changes;
- Plan 006 types cannot be carried as sidecar metadata without a breaking
  schema change;
- validating score entries requires executing GPU inference.

## Maintenance notes

- The adapter is the only intended coupling point from `khalkha_frontend` to
  VocalRender score JSON. Keep all linguistic processing upstream-neutral.
- Reviewers should compare emitted structures to upstream helper behavior and
  reject any silent default.
- If explicit phone conditioning is later proven useful, add a versioned new
  adapter/experiment rather than changing this baseline contract invisibly.
