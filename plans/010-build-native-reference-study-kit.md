# Plan 010: Build the deterministic context-stratified 32-item native-reference study kit

> **Executor instructions**: Implement this plan on `main` without recording or
> generating audio. Preserve unresolved phonology as hypotheses. Subagents may
> prepare changes in the shared tree but must not commit; the primary integrator
> reviews, tests, commits, and pushes with the repository user's configured Git
> identity and no co-author trailers.
>
> **Drift check (run first)**:
> `git diff --stat 1bf7bb8..HEAD -- benchmarks resources experiments reports src/khalkha_frontend scripts/mn tests`
> Reconcile existing changes and never reset or clean unrelated work.

## Status

- **Status**: BLOCKED: qualified Khalkha context/alignment approvals and consented native-singer references required
- **Priority**: P1
- **Effort**: L
- **Risk**: MEDIUM
- **Depends on**: Plan 009
- **Category**: research tooling / evaluation
- **Planned at**: commit `1bf7bb8`, 2026-08-15

## Why this matters

`reports/milestone-0.md` defines the next experiment as 32 balanced items,
eight each for `L`, `G`, `H`, and `PALATALIZATION`, with stable selection,
native references, fixed-score synthesis, and three blinded ratings. Today that
contract is prose only. `benchmarks/MN-PHON-250/audio_manifest.yaml` and
`evaluations.yaml` contain no observations, while
`src/khalkha_frontend/benchmark.py:34-46,167-265` cannot identify a
VocalRender take, blinding session, evaluation criterion, or consent record.
The evidence registry is also empty, so claimed pronunciation evidence cannot
yet be checked mechanically. The benchmark's existing `position` field is not
enough to design the study: the target groups require different vowel,
structural, cluster, nasal, consonant, and palatalization-trigger strata. The
score adapter also requires explicit lyric units, so assigning one note to a
whole multisyllabic word would confound pronunciation with bad lyric-to-note
alignment.

## Current state

- `benchmarks/MN-PHON-250/manifest.yaml` contains 250 items and fields such as
  `target_group`, `legacy_category`, `context`, `position`, `target_grapheme`,
  `left_context`, and `right_context`. These are useful seeds but do not encode
  approved group-specific strata, trigger types, target consonants, or
  hard/soft pair membership.
- `benchmarks/MN-PHON-250/manifest.yaml:2575-2581` identifies
  `MNPHON_161`, text `хүүхэд`, as an H-group front word-initial item; it does
  not contain lyric-unit alignment.
- `src/khalkha_frontend/benchmark.py:86-163` validates benchmark items but has
  no context-annotation or study-quota schema. Its expected-phone fields must
  remain unresolved without evidence.
- `scripts/mn/prepare_score.py:39-109` already requires explicit nonempty
  `units`, each with its own nonempty `notes`; match this shape rather than
  adding a separate score interpretation.
- `reports/milestone-0.md:137-172` describes position-first selection and one
  `<NOTE_2>` at MIDI 60 per item. This plan supersedes those two details because
  they do not control the target contexts or multisyllabic alignment.

## Scope

**In scope (only these paths):**

- `experiments/006_native_reference_study/**` — configs, context/alignment
  approvals, frozen scores/selections, schemas, empty result manifests, README;
- `src/khalkha_frontend/benchmark.py` and `src/khalkha_frontend/__init__.py` —
  study observation types/validation exports;
- `scripts/mn/audit_study_contexts.py`, `select_native_study.py`,
  `validate_study_alignments.py`, and `validate_native_study.py`;
- `resources/phonology/evidence.yaml` and its loader/validator under
  `src/khalkha_frontend/`;
- focused `tests/` fixtures/tests, `reports/milestone-0.md`,
  `experiments/README.md`, and the Plan 010 status row in `plans/README.md`.

**Out of scope:** recording people, model inference, ratings, phonetic rules,
LoRA, raw audio, personal names/contact information, model input changes,
checkpoint/tokenizer/model files, and any other experiment's immutable run
record.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Benchmark baseline | `python scripts/mn/validate_benchmark.py benchmarks/MN-PHON-250/manifest.yaml` | `250 valid items`, exit 0 |
| Context audit | `python scripts/mn/audit_study_contexts.py --config experiments/006_native_reference_study/config/selection_strata.yaml` | every required quota feasible, exit 0 |
| Review queue | `python scripts/mn/select_native_study.py --config experiments/006_native_reference_study/config/study.yaml --emit-review-queue` | append-only review-cycle report, exit 0 |
| Alignment gate | `python scripts/mn/validate_study_alignments.py experiments/006_native_reference_study/config/alignments.yaml` | all queued decisions valid; exit 0 |
| Freeze | `python scripts/mn/select_native_study.py --config experiments/006_native_reference_study/config/study.yaml --freeze` | `32 selected`, all quotas/alignment approvals pass |
| Study gate | `python scripts/mn/validate_native_study.py experiments/006_native_reference_study` | `32 selected, 0 takes, 0 ratings`, exit 0 |
| Unit tests | `python -B -m pytest -q -p no:cacheprovider` | all tests pass |
| Format | `python -m black --check src/khalkha_frontend scripts/mn tests` | exit 0 |
| Lint | `python -m flake8 --max-line-length=120 --extend-ignore=E203 src/khalkha_frontend scripts/mn tests` | exit 0 |

## Implementation contract

### 1. Define group-aware context strata before selection

Add `experiments/006_native_reference_study/config/selection_strata.yaml` with
explicit, versioned context labels and minimum coverage quotas. Every quota has
`id`, `group`, `field`, `allowed_values`, `minimum_count`, and
`required: true|false`. Counts are evaluated independently within one target
group. One item may increment several different quotas but at most once per
quota. Use this exact minimum contract:

| Group | Quota ID | Field/value | Minimum | Required |
|---|---|---|---:|---|
| L | `l_word_initial` | `structural_context=word_initial` | 1 | yes |
| L | `l_intervocalic` | `structural_context=intervocalic` | 1 | yes |
| L | `l_cluster` | `structural_context=preconsonantal_cluster` | 1 | yes |
| L | `l_word_final` | `structural_context=word_final` | 1 | yes |
| L | `l_front_vowel` | `vowel_context_class=front` | 1 | yes |
| L | `l_back_vowel` | `vowel_context_class=back` | 1 | yes |
| L | `l_palatalized` | `trigger_type=explicit_soft_sign|contextual` | 1 | no; secondary |
| G | `g_front_vowel` | `vowel_context_class=front` | 1 | yes |
| G | `g_back_vowel` | `vowel_context_class=back` | 1 | yes |
| G | `g_intervocalic` | `structural_context=intervocalic` | 1 | yes |
| G | `g_word_final` | `structural_context=word_final` | 1 | yes |
| G | `g_cluster` | `structural_context=preconsonantal_cluster` | 1 | yes |
| G | `g_ng` | `cluster_or_ng_context=ng` | 1 | yes |
| G | `g_word_initial` | `structural_context=word_initial` | 1 | no; secondary |
| H | `h_front_vowel` | `vowel_context_class=front` | 1 | yes |
| H | `h_back_vowel` | `vowel_context_class=back` | 1 | yes |
| H | `h_word_initial` | `structural_context=word_initial` | 1 | yes |
| H | `h_intervocalic` | `structural_context=intervocalic` | 1 | yes |
| H | `h_cluster` | `structural_context=preconsonantal_cluster` | 1 | yes |
| H | `h_word_final` | `structural_context=word_final` | 1 | no; secondary |
| PALATALIZATION | `pal_soft_final` | `trigger_type=explicit_soft_sign` and `structural_context=word_final` | 1 | yes |
| PALATALIZATION | `pal_soft_internal` | `trigger_type=explicit_soft_sign` and `structural_context=internal` | 1 | yes |
| PALATALIZATION | `pal_contextual` | `trigger_type=contextual` | 1 | yes |
| PALATALIZATION | `pal_complete_pair` | approved complete `contrast_pair_id` | 1 pair | yes |
| PALATALIZATION | `pal_consonant_diversity` | distinct `target_consonant` values | 3 | yes |
| PALATALIZATION | `pal_trigger_diversity` | distinct values including `explicit_soft_sign` and `contextual` | 2 | yes |

Do not derive `front`, `back`, `contextual`, or the target consonant from an
unstated built-in language rule. Create
`experiments/006_native_reference_study/config/context_annotations.yaml` with:

```yaml
schema_version: 1
benchmark_manifest_sha256: <lowercase SHA-256>
items:
  - item_id: MNPHON_161
    structural_context: [word_initial]
    vowel_context_class: [front]
    cluster_or_ng_context: []
    target_consonant: х
    trigger_type: []
    contrast_pair_id: null
    reviewer_pseudonym: <non-identifying ID>
    review_date: <YYYY-MM-DD>
    review_status: approved
    notes: <study-design annotation only>
contrast_pairs:
  - pair_id: <stable ID>
    hard_item_id: <PALATALIZATION item ID>
    soft_item_id: <PALATALIZATION item ID>
    reviewer_pseudonym: <non-identifying ID>
    review_date: <YYYY-MM-DD>
    review_status: approved
```

All label-bearing fields are lists except the one reviewed
`target_consonant`, nullable `contrast_pair_id`, and approval metadata. A pair
must have exactly two distinct PALATALIZATION members, one hard and one soft;
self-pairs, duplicate membership, cross-group members, missing members, and
unapproved pairs fail. An unresolved alignment for either member excludes the
whole pair.

Existing manifest fields and legacy categories may seed an annotation draft,
but **no label counts toward selection until the item has an explicit
`review_status: approved` record from a qualified Standard Khalkha reviewer**.
Ambiguous/unreviewed labels are ineligible. These are study-design annotations,
not expected phonemes/phones; keep the latter null.

The configuration must distinguish `required` quotas from `secondary`
diversity goals and give every label a short operational definition. Validation
fails on missing labels, unsupported label values, stale benchmark checksum,
an unapproved annotation, an invalid hard/soft pair, or a quota that the current
pool cannot satisfy.

**Verify:** a context-audit command prints per-group candidate counts for every
required and secondary stratum, identifies multi-label items, validates complete
contrast pairs, and exits nonzero if any required quota is infeasible.

### 2. Select by group constraints and context diversity; use the hash only for ties

Add `experiments/006_native_reference_study/config/study.yaml` and a selector
under `scripts/mn/`. For each group, use deterministic branch-and-bound over
eight-item sets (or an equivalently exact in-repository search with no new
solver dependency):

1. reject every set that does not meet all **required group-specific minimums**;
2. treat a declared hard-versus-soft contrast pair as a set-level atomic
   constraint: both member IDs are present or neither is, and a selected pair
   consumes two of the eight slots;
3. among feasible sets, maximize a lexicographic diversity vector declared in
   `selection_strata.yaml`: the number of distinct secondary values for each
   field in the fixed order `structural_context`, `vowel_context_class`,
   `cluster_or_ng_context`, `target_consonant`, `trigger_type` (irrelevant
   fields are omitted per group);
4. only when two sets have the identical feasibility and diversity vector, sort
   each set's member hashes and choose the lexicographically lowest vector of
   SHA-256 values for `mnphon-native-v1:<item_id>`.

The hash therefore cannot cause a lower-context-coverage set or item to win. Do
not use manifest order, manual preference, or raw hash rank as an earlier
objective. Hash the exact UTF-8 bytes of that NFC string, serialize lowercase
64-character hexadecimal, and compare ascending. Compute/report hashes only for
otherwise tied sets; non-tied candidate rows use `tie_break_hash: null`. Emit
the tie cohort explicitly. In the practically impossible case of equal digests,
use ascending item ID only as a collision fallback and emit a warning. The
search must report the number of feasible sets considered and the winning
diversity vector. Use pruning so the exact search is bounded, but test the
result against brute-force enumeration on small fixtures.

In `--emit-review-queue` mode, run the same optimization while provisionally
allowing context-approved items whose lyric alignment is not yet reviewed, then
emit only the winning-set items that need Step 3 review. After reviews are
recorded, recompute: `approved` items remain eligible,
`alignment_unresolved` items are deterministic exclusions, and newly introduced
winning-set items become the next review queue. Repeat until the winning set is
fully approved. `--freeze` is permitted only when all 32 winning items are
approved.

Persist each recomputation as an append-only review cycle containing `cycle_id`,
config/context/alignment-input hashes, provisional winning IDs/pair IDs,
diversity vector, tie cohort, items requiring review, and exclusions inherited
from earlier cycles. Allowed alignment transitions within one study version are
only `unreviewed -> approved` or `unreviewed -> alignment_unresolved`.
Reconsidering a decided alignment requires a new study/config version that
retains the old cycle history; it may not rewrite or reorder prior cycles.

Fail with a coverage-gap report if eight items cannot satisfy every required
quota; never silently relax a quota, borrow an item from another group, or
hand-pick a replacement after hearing model output.

Record source manifest and context-annotation SHA-256 values, selector version,
seed namespace, feasible-set/diversity result, tie-break hashes, selected IDs,
group, satisfied strata, review-queue history, and deterministic exclusions.

**Verify:** two clean runs are byte-identical; output has 32 unique item IDs,
eight per group; every required quota evaluates true; the selection report
shows the winning diversity vector and proves each hash comparison occurred
only between otherwise equal feasible sets.

### 3. Manually adjudicate lyric-to-note alignment before freezing the 32 items

Do not generate one note per benchmark string. The adapter consumes explicit
lyric units (`scripts/mn/prepare_score.py:39-109`), and each unit owns one or
more notes. Create a checked-in pre-freeze alignment manifest containing, for
each candidate reached by the deterministic selector stream:

- the original NFC-normalized `source_text`, item ID, and
  `whitespace_policy: reject_whitespace` for these single-word benchmark items;
- `alignment_complexity: single_unit|multi_unit`, supplied by the reviewer and
  never inferred from spelling;
- an ordered list of manually established raw-Cyrillic lyric units, each with
  `source_span: [start, end]` using zero-based, end-exclusive Unicode scalar
  offsets; spans must be contiguous, non-overlapping, start at 0, end at
  `len(source_text)`, and satisfy `unit.text == source_text[start:end]`;
- one MIDI 60 (`C4`) `<NOTE_2>` per lyric unit for this controlled study;
- reviewer pseudonym, review status, date, and a non-phonetic alignment note;
- `approved`, or `alignment_unresolved` with a reason recorded before synthesis.

Required example:

```yaml
item_id: MNPHON_161
source_text: хүүхэд
whitespace_policy: reject_whitespace
alignment_complexity: multi_unit
lyric_units:
  - text: хүү
    source_span: [0, 3]
    notes:
      - {midi_pitch: 60, note_value: "<NOTE_2>"}
  - text: хэд
    source_span: [3, 6]
    notes:
      - {midi_pitch: 60, note_value: "<NOTE_2>"}
reviewer_pseudonym: <required non-identifying reviewer ID>
review_date: <YYYY-MM-DD>
review_status: approved
alignment_note: <required non-phonetic manual adjudication note>
```

Thus `хүүхэд` is tested as `хүү | хэд` over two C4 notes, never as the whole
word on one C4 note. Monosyllables such as `мал`, `гэр`, and `хөл` may remain
one unit/one note after manual approval. Multisyllabic forms such as `агаар` and
`идэхэд` also require explicit manual adjudication; the code must not guess
their division from character count, vowels, a generic syllabifier, or the
examples in this plan.

The selector first produces the deterministic review queue defined in Step 2
and freezes the final 32 only from `approved` alignments. When a candidate is
`alignment_unresolved`, retain its reason and recompute the constrained optimum;
review any newly introduced candidate before freezing. All alignment review
must finish before inference or listening, so exclusions cannot become
outcome-aware.

For every selected item, materialize the reviewed fixed score at BPM 96. Keep
raw Cyrillic in each lyric unit and preserve benchmark hypotheses only as
metadata. Write exactly one checked-in score per item at
`experiments/006_native_reference_study/config/scores/<item_id>.json`; the file
must use `scripts/mn/prepare_score.py`'s `units` shape and contain exactly one
MIDI-60 `<NOTE_2>` note per unit. Record the alignment-manifest checksum and
each final score checksum.

**Verify:** score validation succeeds for all 32 items; concatenated units
and their spans reconstruct each source item; every unit has exactly one note;
`MNPHON_161` has exactly `["хүү", "хэд"]`, spans `[0,3]`/`[3,6]`, and two
MIDI-60 `<NOTE_2>` notes; all 32 selected items have approved manual alignment,
regardless of `alignment_complexity`.

### 4. Extend benchmark observation schemas

Keep VocalRender outputs under the existing
`AudioSource.BENCHMARK_TTS`/`data/raw/benchmark_tts` semantic root; do not add a
new permanent source directory. Extend `AudioTake` with only research-safe
fields needed to reproduce a take: `system_id` (use `vocalrender_pro` for this
condition), model/base-checkpoint ID, score/config checksums, prompt pseudonym
and provenance, generation seed, inference run ID, sample rate, channels,
duration, and consent reference for human audio. Primary native references use
`AudioSource.NATIVE_SINGING`; require the same selected item ID, lyric units,
score checksum, BPM, MIDI pitches, and note values as the paired VocalRender
take. Optional secondary speech evidence uses `AudioSource.NATIVE_SPEECH`,
matches item text but carries no singing-score claim, and never counts toward
the primary 64-take minimum. Extend ratings with criterion, blind label, session
ID, presentation order, rater-language qualification, and protocol version.
Keep real identities outside Git.

Define machine rules: take IDs and blind labels unique; relative POSIX paths
contained under the source root; checksums lowercase 64-character SHA-256;
native singing takes require approved consent plus score/alignment checksums;
generated takes require all system/score/config/prompt/seed fields; sample rate and duration are positive,
channels are 1 or 2; ratings are integers 0/1/2; the unique rating key is
`(audio_take_id, criterion, rater_pseudonym)`; no rater-facing row exposes take
ID, source, provider, model, prompt, path, or system. The internal hidden map
retains `blind_label -> audio_take_id`; the public worksheet contains only
blind label, criterion, order, protocol, and rating fields.

**Verify:** round-trip tests cover all sources and reject traversal, duplicate
ratings, missing consent, invalid scores, and unblinded records.

### 5. Make evidence references fail closed

Define the minimum `resources/phonology/evidence.yaml` entry: stable ID, claim,
source type/citation, language/variety, locator, review status, allowed use, and
optional artifact checksum. Any resolved benchmark pronunciation or narrow
override must reference an existing entry whose review status and use permit
that claim. Draft/unreviewed entries may annotate a hypothesis but may not
resolve it.

**Verify:** tests reject missing IDs, duplicate IDs, unknown statuses, and a
resolved pronunciation backed only by draft evidence.

### 6. Add study materialization and validation commands

Provide deterministic commands to create checked-in selection/blinding
manifests and validate operator-filled take/rating manifests. Blinding must be
seeded, balanced across presentation order, and stored separately from the
rater-facing sheet. The public worksheet uses blind labels only. Document the
unblinding boundary and append-only corrections.

Expected operator flow:

```powershell
python scripts/mn/audit_study_contexts.py --config experiments/006_native_reference_study/config/selection_strata.yaml
python scripts/mn/select_native_study.py --config experiments/006_native_reference_study/config/study.yaml --emit-review-queue
python scripts/mn/validate_study_alignments.py experiments/006_native_reference_study/config/alignments.yaml
python scripts/mn/select_native_study.py --config experiments/006_native_reference_study/config/study.yaml --freeze
python scripts/mn/validate_native_study.py experiments/006_native_reference_study
python -m pytest -q
```

**Verify:** validation reports `32 selected, 0 takes, 0 ratings` before Plan
012, with a nonzero exit for malformed or partially claimed results.

### 7. Document the protocol without claiming results

The experiment README must specify Standard Khalkha eligibility, consent and
pseudonym handling, recording requirements, randomized blinded playback,
headphone/quiet-room recommendation, 0/1/2 rubric,
and the predeclared recurring-error rule: at least two of three raters score 0
or 1 across at least three items while native-reference median is 2. State that
Music3 is optional and never native ground truth. The README must also state
that this plan's context-stratified selection and reviewed multi-unit scores
supersede the simpler position-only/one-note description in
`reports/milestone-0.md:137-172`; the implementing executor updates that report
to point to the frozen study manifests rather than retaining contradictory
instructions.

Document the two required conditions without conflating them:

- **native reference**: a consented Standard Khalkha singer performs the exact
  manually approved lyric units, notes, MIDI pitches, note values, and BPM used
  by the paired generated condition; the take records the same score checksum;
- **VocalRender condition**: raw-Cyrillic lyric units rendered from the manually
  approved BPM-96/C4/`<NOTE_2>` score under `benchmark_tts`.

The primary conditions share item ID, lexical text, lyric-unit alignment, notes,
and BPM. Plan 012 must use this same-score matrix. Native speech may be added as
secondary segmental evidence with separate consent/provenance, but it is not a
substitute for a missing sung reference and does not count toward the primary
64-take/192-rating minimum.

## Test plan

- Unit-test group-specific quota feasibility, multi-label constrained scoring,
  complete paired selection, hash-only tie-breaking, stable selection, manual
  alignment reconstruction, score invariants, schema round trips, containment,
  evidence resolution, blinding balance, and rating cardinality.
- Include fixtures proving that a position-diverse but G-context-incomplete set
  fails, that a higher-diversity feasible set beats a lower hash, that exact
  search matches brute force on a small pool, and that an unresolved alignment
  deterministically recomputes the review queue without relaxing quotas.
- Include exact regression coverage for `хүүхэд` as two lyric units/two C4
  notes and rejection of a single-unit/single-note version, partial/reordered/
  overlapping spans, extra notes, and inferred rather than reviewer-approved
  alignment.
- Run Black and flake8 on touched Python paths with the repository settings.
- Parse all new YAML/JSON and scan them for absolute paths, secrets, and direct
  speaker identifiers.
- Keep existing 130-test baseline green.

## Done criteria

- [ ] Exactly 32 deterministic items and manually aligned fixed scores are checked in.
- [ ] All group-specific required strata and PALATALIZATION pair/diversity rules pass.
- [ ] SHA-256 is used only to break otherwise equal feasible-set ties.
- [ ] Every selected item has approved explicit lyric units; the
  `хүүхэд` regression is `хүү | хэд` with two C4 `<NOTE_2>` notes.
- [ ] Empty take/rating state validates without pretending the study ran.
- [ ] Observation, consent, blinding, and evidence gates fail closed.
- [ ] The primary condition schema requires matching native-singing and
  VocalRender score/alignment checksums; speech is secondary-only.
- [ ] The study protocol and recurring-error rule are predeclared.
- [ ] No audio, identity, inference result, or phonetic fact is fabricated.

## STOP conditions

Stop if the benchmark checksum differs from the approved annotation input, the
source pool lacks a globally feasible eight-item set for any group, any required
quota depends only on unapproved legacy labels, a context/pair label or lyric
division lacks a qualified reviewer approval artifact, selection requires an
outcome-aware substitution, any item would be assigned notes without reviewed
alignment, consent would expose identity, or a schema/status change would
rewrite an earlier review cycle. Write the failure to
`experiments/006_native_reference_study/results/selection_blocker.json` with
group, quota ID, approved candidate count, missing labels, excluded IDs/reasons,
and additional approvals needed. Do not weaken the design to force 32 items.
Do not begin Plan 012 until Plans 010 and 011 are both done.

## Maintenance notes

Treat selection and blinding manifests as immutable after the first recording.
Context annotations and lyric alignments freeze with selection and are included
in every downstream score checksum. Corrections create a new schema/study
version and retain prior checksums. Permanent paths remain semantic; provenance
belongs in manifests and `DATA_SOURCES.md`.
