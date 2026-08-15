# Plan 019: Run the selected full LoRA adaptation to its declared horizon

> **Executor instructions**: Execute `selected-run.yaml` exactly. This plan
> authorizes one selected full LoRA run, not arbitrary tuning. Work on `main`;
> local checkpoints/logs/audio remain ignored. Parallel agents may monitor or
> independently verify artifacts but must not launch competing runs, alter
> configs, or commit. The primary integrator controls launch/resume, validates,
> commits metadata, and pushes with the user's Git identity and no co-author trailers.
>
> **Drift check (run first)**:
> `git diff --stat 1bf7bb8..HEAD -- experiments/008_lora_pilots experiments/009_full_lora_training conf data/manifests reports src scripts tests`

## Status

- **Status**: TODO
- **Priority**: P1
- **Effort**: XL
- **Risk**: HIGH
- **Depends on**: Plan 018; Plan 015B conditionally for multi-rank,
  preemptible-cloud, or shared/network-filesystem runs
- **Category**: training execution
- **Planned at**: commit `1bf7bb8`, 2026-08-15

## Goal

Complete the one preselected Mongolian LoRA adaptation to the exact declared
`total_steps`, producing a verified final adapter checkpoint and an immutable
training-completion record. “Training complete” means the mechanics finished;
it does not mean the model passed evaluation or is approved for release.

## Preconditions

The executor must verify, by hash and status:

- Plans 013–017 artifacts and lifecycle tests are complete;
- Plan 018 selected one passing candidate and froze `selected-run.yaml` plus
  `acceptance.yaml` with operator/native-evaluator approval;
- approved corpus, frozen splits, compiled annotations, preprocessed shards,
  base checkpoint, tokenizer, AudioVAE, code, config, and metric assets match;
- GPU topology, precision support, free VRAM, projected wall time, checkpoint/
  log storage, retention, and interruption handling meet the declared budget;
- `selected-run.yaml` uses `world_size == 1`, non-preemptible execution, and an
  approved local checkpoint filesystem, **or** Plan 015B is DONE for the exact
  distributed/scheduler/filesystem profile;
- no unrelated training process writes to the run directory.

Any mismatch creates a new run proposal and returns to Plan 018; do not patch
the selected config in place.

## Execution

### 1. Create the immutable run record

Materialize `experiments/009_full_lora_training/results/<run-id>/run.json` in
`created` state with the full Plan 015A provenance manifest, selected-run and
acceptance hashes, expected total steps, expected final checkpoint tag
`step_(total_steps-1)`, budgets, and operator start approval. Use a unique local
output directory; never reuse or delete a prior run.

### 2. Launch through fail-closed preflight

Run the exact registered command/config. Verify trainable parameter inventory
matches the selected adapter, data loader sees only frozen train/validation
splits, prompt policy is valid, and initial loss/gradients are finite. Persist
the sanitized launch environment and transition to `running` atomically.

### 3. Monitor without tuning

Monitor heartbeat, step/LR/loss/gradient health, samples/tokens seen, evaluation
completeness, VRAM/storage, checkpoint integrity, and wall-clock budget. Do not
change LR, rank, scope, data, seed, schedule, total steps, or thresholds based on
intermediate results. A normal interruption resumes the same run from verified
`latest`; it is not a new trial.

Alert/stop on nonfinite values, repeated data errors, invalid checkpoint,
unexpected trainable weights, resource danger, provenance drift, or incomplete
required validation. Preserve the last good checkpoint and failure evidence.

### 4. Verify mechanical completion

After exit code 0, independently require:

- all declared steps executed exactly once across original/resumed segments;
- final permanent checkpoint is tagged at `total_steps - 1`;
- runtime state has `next_step == total_steps`;
- checkpoint manifest, adapter config/weights, optimizer/scheduler/RNG state,
  and `latest` resolve and hash correctly;
- losses/gradients required by policy contain no NaN/Inf;
- input/provenance hashes and trainable parameter inventory never drifted;
- Plan 016 dry-run loads the adapter against the frozen base and one bounded
  diagnostic inference produces a valid ignored WAV.

Only then transition to `training_complete`, followed by
`checkpoint_published` for the verified local checkpoint. Do not set
`evaluation_complete` or `release_approved`.

### 5. Commit only small evidence

Commit sanitized configs, manifests, aggregate curves/downsampled metrics,
failure/interruption history, verification output, and the completion report.
Never stage checkpoint tensors, optimizer state, raw/preprocessed audio, latents,
full logs with paths/identities, or generated WAVs.

## Verification commands

Use the entry points established by Plans 015A, 016, and 017:

```powershell
python scripts/check_runtime.py --require-cuda --task train --config experiments/008_lora_pilots/config/selected-run.yaml
python scripts/train_vocalrender_svs.py --config_path experiments/008_lora_pilots/config/selected-run.yaml
python scripts/verify_training_run.py --run-dir checkpoints/<selected-run-id> --require-state training_complete
python scripts/verify_checkpoint.py checkpoints/<selected-run-id>/latest
python scripts/infer_vocalrender_svs_single.py --ckpt_dir pretrained_models/VocalRender-Pro --lora_dir checkpoints/<selected-run-id>/latest --verify-checkpoint
python -m pytest -q
```

Record resolved commands and exit codes in the run record. All verifiers must
exit 0; the training command alone is insufficient proof of completion.

## Done criteria

- [ ] The selected run reaches exactly its frozen horizon without semantic drift.
- [ ] Final checkpoint, `latest`, hashes, and runtime next-step are verified.
- [ ] Adapter loads against the frozen base and only expected tensors were trained.
- [ ] Run state is `checkpoint_published`, not evaluation/release approved.
- [ ] Only sanitized small evidence is committed; large artifacts remain local.

## STOP conditions

Stop and mark failed/interrupted on data/config/hash drift, nonfinite training,
checkpoint corruption, unexpected parameter mutation, unresolved storage/VRAM
risk, repeated evaluation incompleteness, or a requested hyperparameter/horizon
change. Return to Plan 018 or author a new plan; never continue ad hoc.

## Maintenance notes

The upstream large-scale recipe is contextual evidence, not this run's default.
Only the frozen Plan 018 selection defines the budget. Preserve rejected and
interrupted run records alongside the successful one.
