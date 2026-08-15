# Plan 014: Compile and validate score-aligned Mongolian SVS annotations

> **Executor instructions**: Start only with a Plan 013-approved native-singing
> corpus and the frozen Plan 012 input decision. Work on `main`; raw annotations
> and outputs remain local/ignored. Subagents do not commit. The primary
> integrator reviews, tests, commits metadata, and pushes with the user's Git
> identity and no co-author trailers.
>
> **Drift check (run first)**:
> `git diff --stat 1bf7bb8..HEAD -- src/vocalrender/preprocessing src/vocalrender/training scripts conf data/manifests tests docs`

## Status

- **Status**: BLOCKED: no approved native Standard Khalkha score-aligned singing corpus is available
- **Priority**: P1
- **Effort**: XL
- **Risk**: HIGH
- **Depends on**: Plans 012, 013
- **Category**: data pipeline / annotation quality
- **Planned at**: commit `1bf7bb8`, 2026-08-15

## Why this matters

The upstream preprocessing path can silently drop samples
(`src/vocalrender/preprocessing/data_loaders.py:242-246,678-748` and
`arrow_writer.py:280-282,343-346`). It joins annotation paths using
`audio_root / wav_fn` at `data_loaders.py:418,541` without a strong containment
contract. Score tensor conversion also accepts weak/unknown values, and malformed
note duration/BPM can reach downstream math. A training corpus must therefore
be compiled through a strict neutral schema before AudioVAE preprocessing.

## Scope

**In scope:** neutral annotation schema, split-specific compiler into the exact
upstream dataset format, audio/score/path validation, quarantine accounting,
aggregate/hash manifests, capped validation command, and tests.

**Out of scope:** modifying raw audio, auto-correcting lyrics/pitches, VAE
preprocessing, training, phoneme injection, committing local annotations, or
silently skipping failures.

## Steps

### 1. Define a neutral annotation record

For every utterance store corpus/split/item IDs; pseudonymous singer/song/session;
contained relative WAV path and checksum; sample rate/channels/duration; exact
raw Cyrillic words; integer MIDI pitches; supported note tokens/durations;
`pitch2word`; positive finite BPM; aligned start/end times where available; and
the frozen raw-Cyrillic/narrow-override decision provenance. Require exact array
cardinality and melisma invariants.

Reject unsupported note tokens, BPM <= 0, NaN/Inf, non-MIDI pitches, empty text,
misalignment, duplicate IDs/checksums, path traversal, symlink escape, missing
audio, clipping/zero-length audio, and split mismatch. Never substitute a
quarter note or zero pitch for malformed strong labels.

### 2. Compile three explicit upstream datasets

Emit local ignored annotations/config for `mn_native_train`,
`mn_native_validation`, and `mn_native_test`, preserving Plan 013 splits.
Compilation is deterministic and atomic. Each output record carries source
item/checksum so it can be traced back without PII. Do not merge validation or
test into training prompt pools.

Check in only schema/config, aggregate counts/durations, excluded-reason counts,
and content hashes under `data/manifests/mn_svs/`. Full paths and annotation
content stay local.

### 3. Replace silent skips with an auditable mode

For this Mongolian pipeline, any invalid/missing sample causes nonzero exit by
default. An explicit `--quarantine-invalid` mode may finish only when it writes
an itemized local quarantine file plus checked-in aggregate, and the operator
accepts the reduced frozen manifest before preprocessing. The script's final
status must include discovered, compiled, quarantined, and emitted counts and
must never print success when counts disagree.

Strengthen root containment before file access. Tests must include `..`,
absolute paths, alternate separators, and a symlink that escapes the root.

### 4. Validate prompt candidates and token budget estimates

Precompute same-song, non-overlapping prompt candidates per split and reject
targets without a valid prompt when `prompt_audio_prob=1.0`. Account for maximum
prompt frames, not an average estimate, when proving a sample fits
`max_batch_tokens`; `src/vocalrender/training/svs_data.py:686-687` currently
uses approximate overhead. Oversized targets are explicit exclusions, never
runtime surprises.

### 5. Produce a pre-preprocessing readiness report

Report eligible/compiled/quarantined items and hours per split, singer/song
group counts, score/pitch/duration ranges, prompt coverage, maximum token/frame
budget, duplicate checks, and all input/output hashes. Sign off this report
before Plan 017.

## Verification commands

```powershell
python scripts/mn/compile_svs_annotations.py --config conf/mn_svs_compile.yaml --validate-only
python scripts/mn/compile_svs_annotations.py --config conf/mn_svs_compile.yaml
python scripts/mn/validate_svs_annotations.py --manifest data/manifests/mn_svs/compiled.yaml
python -m pytest -q
```

Run twice in a clean temporary output and compare manifests byte-for-byte. Run
Black/flake8 and the upstream score-adapter regression suite.

## Done criteria

- [ ] All strong-label score/audio invariants fail closed.
- [ ] Train/validation/test outputs exactly preserve frozen groups.
- [ ] Every discovered item is compiled or explicitly quarantined; counts balance.
- [ ] Paths are contained and prompt targets do not overlap.
- [ ] Only hashes/aggregates/config are committed; no audio, PII, or annotations.

## STOP conditions

Stop if approved audio lacks score alignment, compilation needs guessed notes or
lyrics, any split leak exists, invalid rate exceeds the operator's predeclared
tolerance, or local storage cannot hold atomic outputs. Do not preprocess a
partial corpus under a success label.

## Maintenance notes

Compiler version, config, corpus/split hashes, and output hashes form one
immutable dataset identity. Any correction creates a new identity and requires
downstream preprocessing again.
