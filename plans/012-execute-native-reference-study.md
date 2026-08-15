# Plan 012: Execute the 32-item same-score native-singing study

> **Executor instructions**: Execute the frozen Plan 010 protocol only after a
> successful Plan 011 CUDA smoke. This plan requires real human participants;
> software agents may build/validate manifests but must never fabricate a
> singer, consent, recording, or rating. Work on `main`; raw audio and identity
> records remain local and ignored. Subagents do not commit. The primary
> integrator preserves blinding, reviews evidence, commits sanitized metadata,
> and pushes with the user's configured Git identity and no co-author trailers.
>
> **Drift check (run first)**:
> `git diff --stat 1bf7bb8..HEAD -- experiments/006_native_reference_study benchmarks resources/phonology data/raw reports tests`

## Status

- **Status**: BLOCKED: native singer, consented same-score recordings, and three qualified raters required
- **Priority**: P1
- **Effort**: XL
- **Risk**: HIGH
- **Depends on**: Plans 010, 011
- **Category**: experiment / human evaluation
- **Planned at**: commit `1bf7bb8`, 2026-08-15

## Goal and acceptance contract

Run a matched singing comparison for the 32 frozen items:

```text
              SAME TEXT
          SAME LYRIC UNITS
          SAME NOTES + BPM
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
Native Standard       VocalRender-Pro
Khalkha singer        raw Cyrillic
        │                   │
        └─────────┬─────────┘
                  ▼
           blinded ratings
```

The primary minimum is exactly 64 valid takes: one consented native Standard
Khalkha **sung** reference and one raw-Cyrillic VocalRender-Pro rendition for
each item. Both use the identical frozen score checksum. Obtain at least 192
primary ratings: three independent eligible raters for each of the 64 takes.

Native speech may be collected as secondary segmental evidence, but it does not
replace sung references or count toward the 64/192 primary minimum. If 32 speech
takes are added and rated by all three raters, report 96 total takes and 288
total ratings while keeping primary and secondary completeness separate.

This is a diagnostic/development study, not a final test set. It may identify
raw-Cyrillic failures or evidence-backed narrow override candidates; it does not
justify broad G2P rules or provide training permission.

## External prerequisites and human bottleneck

Before changing status to `IN PROGRESS`, the operator must provide:

- at least one verified native Standard Khalkha singer able to perform all 32
  frozen scores;
- signed or otherwise explicit, auditable consent covering recording, private
  storage, blinded research evaluation, and the intended reporting scope;
- at least three qualified native Standard Khalkha raters who can finish the
  full protocol;
- a private identity/consent store and pseudonymous IDs referenced by manifests;
- a recording setup and schedule sufficient to obtain all 32 sung references.

The reference singer must not count as a required independent rating of their
own takes. Evaluation consent does **not** grant model-training, redistribution,
or public-release rights. If any prerequisite is absent, mark the plan
`BLOCKED: external singer/consent/raters/recordings unavailable`; do not create
synthetic stand-ins.

## Scope

**In scope:** consented same-score singing recording, metadata capture,
VocalRender rendering, optional secondary speech, blinded presentation,
criterion-specific ratings, predeclared analysis, evidence links, and a
sanitized decision record.

**Out of scope:** model training, admitting reference recordings to the training
corpus, changing frozen items/scores after recording or listening, automatic
phone scoring, substituting speech for singing, committing raw audio/consent/PII,
and treating Music3 as native ground truth.

## Execution

### 1. Revalidate the frozen study and participant approvals

Verify Plan 010's benchmark, context, selection, alignment, and 32 score
checksums. Confirm every score has manually approved lyric units and exactly one
C4 `<NOTE_2>` per unit at BPM 96. Validate singer/rater pseudonyms and consent
references without reading identity material into Git.

Create an immutable protocol record with participant-role separation, recording
specification, retry policy, rating criteria, expected counts, blinding seed,
and the explicit primary/secondary condition matrix.

**Verify:**
`python scripts/mn/validate_native_study.py experiments/006_native_reference_study --phase prerecording`
→ `32 scores, singer approved, 3 raters approved, 0 takes`, exit 0.

### 2. Record 32 score-matched native-singing references

For each item, the singer performs the exact Plan 010 text, lyric-unit division,
MIDI pitches, note values, and BPM. Use a count-in or accompaniment method that
does not alter the target score. Capture lossless audio in a consistent quiet
setup and record sample rate, channels, duration, score/alignment checksum,
session pseudonym, singer pseudonym, consent reference, and take-selection reason.

Define the retry policy before recording. Retake only for documented technical
or score-performance failure such as clipping, interruption, wrong text/note,
or timing outside the predeclared tolerance. Never cherry-pick based on whether
the singer resembles VocalRender. Retain rejected-take metadata privately.

**Gate:** exactly 32 primary native-singing takes exist, decode, are nonempty and
unclipped under the declared limit, match frozen score checksums, and have
approved evaluation consent. Missing or off-score items block the study.

### 3. Render 32 matched VocalRender-Pro takes

Run VocalRender-Pro with raw-Cyrillic lyric units and the identical frozen score
for each paired native take, using the Plan 011 environment, declared clean
prompt policy, and one predeclared generation seed. A retry is allowed only for
documented technical failure, never pronunciation cherry-picking. Persist
run/config/prompt/base-checkpoint, score/alignment, and output checksums.

**Gate:** exactly 32 primary generated takes validate; each has a one-to-one
item/score match with its native-singing pair, and no frozen input changed.

### 4. Optionally collect secondary native speech

If separately consented, record one Standard Khalkha spoken take per selected
text. Speech matches text but carries no score-performance claim. Store and
analyze it as `secondary_speech`; never use it to satisfy a missing primary
sung take or training-corpus requirement. Predeclare whether speech will be
rated; incomplete optional speech cannot invalidate an otherwise complete
primary study but must be reported honestly.

### 5. Conduct criterion-separated blinded ratings

Generate balanced orders from the frozen blinding manifest. Raters must not see
source, model, singer, filename, hypothesis group, score condition, or other
ratings. Collect at least these separate 0/1/2 criteria:

- `target_articulation`: acceptability of the declared target realization;
- `score_fidelity`: whether text/notes/timing follow the supplied score;
- optional `overall_singing_quality`, reported separately and never used alone
  as phonological evidence.

The primary minimum of 192 refers to `target_articulation`: 64 takes × 3
distinct raters. If `score_fidelity` is also release-gating, predeclare and count
its additional 192 ratings separately. The singer cannot supply a required
rating for their own take. Corrections are append-only with reason.

**Gate:** every primary take has three distinct eligible
`target_articulation` ratings, no duplicate `(take, criterion, rater)` key
exists, and blinding stayed intact.

### 6. Analyze with the predeclared rule

Unblind only after completeness validation. Report paired native-singing versus
VocalRender scores by group/context/item, score-fidelity failures, rater
agreement, missingness, and optional speech evidence separately. A poor native
singing performance cannot establish a phonological fact; any native take that
fails the frozen score-fidelity gate invalidates that pair and therefore blocks
primary completeness.

Flag a recurring generated error only when at least two of three raters score
the VocalRender `target_articulation` 0 or 1 across at least three distinct
items while the score-matched native-singing references have median 2. Preserve
contrary evidence. A proposed narrow override additionally needs reviewed
registry evidence for the same scope; otherwise retain `research_required`.

### 7. Publish a bounded decision record

Write a sanitized immutable result with expected/actual counts, all input and
score hashes, protocol version, exclusions, optional speech coverage, analysis
version, and one decision: `raw_cyrillic`, `narrow_override_candidates`, or
`inconclusive`. State that MN-PHON-32 remains development evidence and that
reference-recording evaluation permission is not training permission.

## Verification

```powershell
python scripts/mn/validate_native_study.py experiments/006_native_reference_study --phase recorded
python scripts/mn/validate_native_study.py experiments/006_native_reference_study --phase rated
python -B -m pytest -q -p no:cacheprovider
python -m black --check src/khalkha_frontend scripts/mn tests
python -m flake8 --max-line-length=120 --extend-ignore=E203 src/khalkha_frontend scripts/mn tests
```

The recorded phase expects `64 primary takes`; the rated phase expects
`64 primary takes, 192 target_articulation ratings`. Scan committed material for
identities, absolute paths, audio, consent documents, secrets, and outcome-aware
changes to frozen scores/selections.

## Done criteria

- [ ] 32 native-singing and 32 VocalRender takes share exact score checksums.
- [ ] At least 192 valid blinded primary articulation ratings meet the protocol.
- [ ] Singer, consent, and three-rater approvals are real and auditable outside Git.
- [ ] Speech, if present, is secondary and cannot satisfy primary completeness.
- [ ] Analysis separates articulation, score fidelity, and overall singing quality.
- [ ] Only sanitized metadata/results are committed; raw audio, consent, and PII stay private.

## STOP conditions

Stop if the singer, explicit evaluation consent, all 32 sung references, or
three completing independent raters are unavailable; any primary take is
off-score or untraceable; blinding is compromised; a frozen item/score must
change; CUDA smoke no longer passes; or required results are incomplete. Mark
the exact external/data blocker. Do not impute ratings, reuse one person as
multiple raters, substitute speech/synthetic audio, or proceed to training to
compensate.

## Maintenance notes

Any rerun is a new study version with new blind labels and retained prior
records. Corrections never rewrite original observations. If these recordings
are ever proposed for training, Plan 013 must independently establish explicit
training and derivative-model rights.
