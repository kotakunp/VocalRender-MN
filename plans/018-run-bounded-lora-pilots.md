# Plan 018: Run bounded LoRA pilots and freeze the full-run decision

> **Executor instructions**: Use only frozen train/validation data and the
> Plan 017-verified pipeline. Work on `main`; checkpoints/audio stay ignored.
> Parallel agents may execute predeclared candidates on separate run/output
> directories but must not edit shared selection results or commit. The primary
> integrator validates comparability, makes the final selection, commits, and
> pushes with the user's Git identity and no co-author trailers.
>
> **Drift check (run first)**:
> `git diff --stat 1bf7bb8..HEAD -- experiments conf reports data/manifests src scripts tests`

## Status

- **Status**: TODO
- **Priority**: P1
- **Effort**: XL
- **Risk**: HIGH
- **Depends on**: Plans 012, 017
- **Category**: experiment / model selection
- **Planned at**: commit `1bf7bb8`, 2026-08-15

## Why this matters

The [upstream VocalRender-Pro paper](https://arxiv.org/html/2607.27768v1)
initialized from VoxCPM2 and reports a large full-model training regime, but
this project has a much smaller, rights-gated Mongolian corpus and intends
parameter-efficient adaptation. Copying the upstream 160k-step, four-H100 recipe
is not evidence for a safe LoRA horizon. Bounded pilots must determine whether
adaptation is learnable and improves a frozen Mongolian validation set before
spending the full-run budget. Chinese is served by the unchanged base with the
Mongolian adapter omitted/disabled; Chinese controls therefore verify routing
and detect catastrophic adapter breakage, not require equal Mandarin quality
with the Mongolian adapter enabled.

## Pre-registration

Before launching any candidate, create immutable
`experiments/008_lora_pilots/config/pilots.yaml` containing:

- exact base/data/preprocessed/code/tokenizer/AudioVAE hashes;
- two adapter scopes: **A** language-model attention/MLP only; **B** the same
  plus explicitly enumerated DiT/projection targets supported by the model;
- initial bounded defaults: rank 8, alpha 16, dropout 0.05, learning rate
  `1e-4`, at most 1,000 optimizer steps per seed;
- seeds 42 and 314159 when budget permits; if only one seed is approved, state
  that limitation before results;
- identical effective batch/token budget, scheduler, precision, prompt policy,
  validation items/prompts/seeds, checkpoint cadence, and wall-time/VRAM/storage
  caps;
- base-model comparison and three bundled upstream Chinese control items in two
  modes: adapter disabled for base-route integrity, and adapter enabled for
  catastrophic-validity diagnostics;
- predeclared automatic completeness gates and human-listening procedure.

The pilot may reduce batch size for measured hardware, but all candidates must
retain comparable effective token exposure. Any changed value creates a new
pilot version; never edit a launched config.

## Execution

### 1. Prove candidate target sets

Use a dry-run report to list every trainable tensor, shape, parameter count, and
module scope. Candidate B must not accidentally unfreeze the base model,
AudioVAE, or unsupported modules. Require nonzero gradients on expected targets
during the Plan 017-style smoke.

### 2. Run bounded pilots independently

Run each registered candidate/seed in a distinct immutable directory. Enforce
resource preflight, lifecycle/checkpoint contracts, nonfinite failure, and the
1,000-step/wall-time cap. Interrupted jobs may resume the same run; they cannot
change semantic config. Do not inspect final test data.

### 3. Evaluate matched validation outputs

Use Plan 016 to generate base and candidate outputs for the exact same frozen
native-singing validation targets, prompts, and seeds plus three Chinese
controls. Required automatic metrics must complete, but they are supporting
signals rather than native pronunciation truth. Run blinded native listening
on a predeclared subset with at least three raters where feasible. Report paired
per-item outcomes, variance across seeds, training stability, runtime, VRAM,
adapter size, and control regressions.

For Chinese controls, predeclare two different interpretations:

- **adapter disabled/omitted**: this is a hard integrity gate. With the same
  seed/config, routing must load the untouched VocalRender-Pro base and reproduce
  the established base path within the deterministic/numerical tolerance defined
  by Plan 016. Any base mutation or inability to disable the adapter fails.
- **Mongolian adapter enabled**: require successful load, finite/nonempty valid
  audio, expected duration/rate/channel bounds, and intact score/prompt
  conditioning. Crash, hang, NaN/Inf, silence/empty output, gross clipping, or
  broken conditioning is catastrophic and fails. Moderate Mandarin quality or
  metric degradation is reported but cannot veto a substantially better
  Mongolian candidate.

MN-PHON-32 may be reported as a disclosed diagnostic only. It cannot choose a
candidate using the final native-singing test split.

### 4. Apply a frozen selection rule

Before evaluation, check in `selection-policy.yaml` with minimum completeness,
stability, Mongolian native-validation improvement, adapter-disabled Chinese
base-route integrity, and adapter-enabled catastrophic-validity predicates.
Do not include moderate Mandarin-quality regression as a selection threshold.
Declare practical Mongolian tie margins. If candidates are within the tie margin
and both pass, select the smaller adapter (normally A). If neither clears all
Mongolian and hard-integrity gates, stop; do not run full training.

The report must include all candidates/seeds, including failures. No selective
rerun may replace an unfavorable seed unless the original was a documented
infrastructure failure.

### 5. Freeze full-run and final acceptance inputs

Only after a passing choice, create:

- `selected-run.yaml`: chosen scope/hyperparameters, exact total step horizon,
  batch/tokens, schedule, seeds, hardware/storage budget, save/eval cadence,
  immutable input hashes, and interruption policy;
- `acceptance.yaml`: final Plan 020 dataset/version, expected item/take/metric/
  rating counts, Mongolian criteria/paired thresholds, adapter-disabled routing
  integrity, adapter-enabled catastrophic-validity checks, missing-data policy,
  and pass/reject logic. Chinese-with-adapter quality deltas are report-only.

These files require operator and native-evaluator sign-off before Plan 019 and
cannot be modified after the final test is examined.

## Verification

- Launch registered runs only through their immutable configs, for example:

  ```powershell
  python scripts/train_vocalrender_svs.py --config_path experiments/008_lora_pilots/config/candidate-a-seed-42.yaml
  python scripts/verify_training_run.py --run-dir checkpoints/<pilot-run> --require-state checkpoint_published
  python scripts/evaluate_vocalrender_svs.py --config experiments/008_lora_pilots/config/evaluation.yaml --require-complete --offline
  python scripts/mn/select_lora_candidate.py --policy experiments/008_lora_pilots/config/selection-policy.yaml --results experiments/008_lora_pilots/results
  ```

  Selection exits 0 only when one registered candidate clears every frozen gate;
  a no-winner result exits nonzero and blocks Plan 019.
- Validate all candidate run/checkpoint/evaluation manifests and expected counts.
- Recompute selection from per-item records with a separate command.
- Confirm final test hashes were not opened by pilot commands.
- Run full pytest, Black, flake8, and scan staged files for large artifacts/PII.

## Done criteria

- [ ] Both registered scopes and declared seeds completed or have honest failures.
- [ ] Validation comparisons are matched, complete, and include Chinese controls.
- [ ] Chinese base routing is a hard integrity gate; enabled-adapter Mandarin
  quality is report-only unless generation/conditioning is catastrophically broken.
- [ ] A predeclared rule selects one passing candidate, or the plan stops rejected.
- [ ] `selected-run.yaml` and `acceptance.yaml` are frozen before final testing.
- [ ] No final test access, unregistered tuning, or artifact upload occurred.

## STOP conditions

Stop if no candidate passes, candidate inputs differ, fewer than the declared
ratings/metrics complete, adapter-disabled base routing differs, an
adapter-enabled Chinese control is catastrophically invalid, final test data is
accessed, or budgets are exceeded. Do not stop merely for a moderate Mandarin
quality decline with the Mongolian adapter enabled. A failed pilot requires a
new plan/version, not an opportunistic full run.

## Maintenance notes

Pilot outcomes remain part of the model card, including negative results. The
smallest passing adapter is preferred when Mongolian quality is practically
tied. This policy assumes serving can omit/disable LoRA for Chinese; if the
deployment cannot route that way, stop and create a new multilingual acceptance
plan instead of silently changing this selection rule.
