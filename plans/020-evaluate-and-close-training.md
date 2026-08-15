# Plan 020: Evaluate the final adapter and close training with an acceptance report

> **Executor instructions**: Evaluate the Plan 019 checkpoint once against the
> frozen Plan 018 acceptance contract. Work on `main`; audio/checkpoints remain
> ignored. Parallel agents may generate independent base/adapter conditions or
> verify statistics only when they use immutable manifests and separate output
> roots; they do not commit. The primary integrator preserves blinding, makes the
> pass/reject call, commits, and pushes with the user's Git identity and no
> co-author trailers.
>
> **Drift check (run first)**:
> `git diff --stat 1bf7bb8..HEAD -- experiments/009_full_lora_training experiments/010_final_evaluation reports benchmarks data/manifests tests docs`

## Status

- **Status**: TODO
- **Priority**: P1
- **Effort**: XL
- **Risk**: HIGH
- **Depends on**: Plan 019
- **Category**: final evaluation / release decision
- **Planned at**: commit `1bf7bb8`, 2026-08-15

## Goal

Compare the frozen base and final adapter on the untouched native-singing test
split, apply the already signed `acceptance.yaml` without modification, and
produce one auditable outcome: accepted candidate or completed-but-rejected
training. No upload or public release is authorized by this plan.

## Required evaluation matrix

- **Primary:** matched base versus adapted outputs for every item in the frozen
  native-singing test split, with identical score, prompt policy, and registered
  seeds.
- **Human:** at least three qualified blinded native Standard Khalkha raters per
  required take/criterion, using the frozen rubric and balanced order.
- **Controls:** three frozen upstream Chinese items in adapter-disabled and
  adapter-enabled modes. Disabled mode is a hard base-routing integrity gate;
  enabled mode is a catastrophic-validity gate, while moderate Mandarin quality
  change is report-only.
- **Diagnostic only:** the 32-item MN-PHON study may be rerun and disclosed but
  cannot replace primary test results or change acceptance thresholds.
- **Automatic:** only predeclared, locally pinned metric backends, with complete
  expected counts and per-item records.

Exact items, criteria, seeds, counts, practical margins, missing-data behavior,
and thresholds come exclusively from the hash-frozen Plan 018
`acceptance.yaml`. If that file is absent or was changed after test access,
evaluation is invalid and must stop.

## Execution

### 1. Verify freeze and create blind manifests

Validate the final adapter/base/run/input hashes and `checkpoint_published`
state. Log the first test-data access timestamp. Generate balanced blind labels
and rater sheets without source/model identifiers. Keep the unblinding key under
operator control until all required ratings are locked.

### 2. Generate the matched matrix once

Use Plan 016 comparison tooling. Every base/adapter pair shares item, score,
prompt, seed, decoding configuration, and environment. Technical retries follow
the frozen policy and cannot cherry-pick audio. Validate every WAV and manifest;
generation count mismatch fails the evaluation.

### 3. Complete human and automatic evaluation

Collect ratings without revealing hypotheses or pilot results. Lock records,
validate unique rater/take/criterion tuples and required cardinality, then
unblind. Run required automatic metrics offline. A missing required metric or
rating makes the evaluation incomplete, not partially passed.

Report paired item-level deltas, confidence/uncertainty appropriate to sample
size, rater agreement, group breakdowns, Chinese-control routing/validity and
quality deltas, metric coverage, failures, and qualitative comments stripped of
identity. Do not use automatic metrics as proof of pronunciation correctness.
Do not reject for moderate Mandarin degradation with the Mongolian adapter
enabled; reject only failed adapter-disabled base equivalence or predeclared
catastrophic enabled-adapter behavior.

### 4. Apply acceptance mechanically

Run a deterministic acceptance command that reads frozen thresholds and
per-item results and emits `pass` or `reject` with every predicate. The executor
may not waive a failed predicate after hearing outputs.

- **Pass:** transition to `evaluation_complete`, write a model card and
  acceptance report, then mark the candidate `release_approved` only for local
  project use defined by the contract.
- **Reject:** record “training run complete, candidate rejected,” identify failed
  predicates, and preserve all evidence. Do not extend training, retune, swap
  checkpoints, or rerun selected items. Further work requires Plan 021.

### 5. Document artifacts and limitations

The final report/model card includes base/adapter fingerprints, eligible corpus
and split summaries, training/pilot provenance, intended/forbidden uses,
language/voice limitations, human protocol, complete results, known failures,
rights constraints, reproduction commands, and storage location by relative
identifier/hash. It explicitly states that release approval is not permission
to upload to Hugging Face or any external service.

## Verification

- Run the frozen evaluation and decision interfaces:

  ```powershell
  python scripts/evaluate_vocalrender_svs.py --config experiments/010_final_evaluation/config/evaluation.yaml --require-complete --offline
  python scripts/mn/validate_native_study.py experiments/010_final_evaluation
  python scripts/mn/apply_acceptance.py --contract experiments/008_lora_pilots/config/acceptance.yaml --results experiments/010_final_evaluation/results
  python -m pytest -q
  ```

  Evaluation/manifest validation must exit 0 before acceptance runs; acceptance
  exits 0 only for a valid complete decision record, whether its result is
  `pass` or `reject`.
- Independently recompute expected versus actual generation/rating/metric counts.
- Recompute the acceptance result from raw per-item records.
- Confirm test hashes were untouched before the recorded first-access time and
  `acceptance.yaml` did not change afterward.
- Run full pytest, Black, flake8, manifest checks, privacy scan, and Git staged
  artifact-size/type scan.

## Done criteria

- [ ] Every frozen primary/control output and required rating/metric is complete.
- [ ] Base/adapter comparison is matched and remained blinded until lock.
- [ ] Chinese controls apply hard routing/catastrophic predicates only;
  enabled-adapter Mandarin quality deltas remain report-only.
- [ ] Frozen acceptance predicates are evaluated mechanically without waiver.
- [ ] Outcome is either accepted or honestly completed-but-rejected.
- [ ] Model card/report is self-contained; no private/large artifact is committed.
- [ ] No external upload or publication occurred.

## STOP conditions

Stop if acceptance thresholds changed after test access, any required count is
missing, blinding is compromised, inputs/checkpoint drift, metric assets are
unpinned/unavailable, rights prohibit evaluation, or someone requests selective
reruns. Invalidation requires a new protocol/plan, not silent repair.

## Maintenance notes

Final test evidence is immutable. Any later model iteration is a new candidate
with a new plan and must preserve this result, including rejection.
