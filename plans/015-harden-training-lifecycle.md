# Plan 015A: Harden the required single-GPU training lifecycle

> **Executor instructions**: Implement only the correctness needed for a local
> single-GPU 4070-class LoRA experiment, using tiny synthetic CPU fixtures and
> bounded one-GPU integration checks. Do not build multi-rank/cloud preemption
> infrastructure; that belongs to Plan 015B. Work on `main`. Subagents do not
> commit; the primary integrator reviews, tests, commits, and pushes with the
> user's configured Git identity and no co-author trailers.
>
> **Drift check (run first)**:
> `git diff --stat 1bf7bb8..HEAD -- src/vocalrender/training src/vocalrender/preprocessing scripts conf tests pyproject.toml`

## Status

- **Status**: BLOCKED: implementation and CPU tests complete; one-GPU lifecycle validation requires CUDA hardware
- **Priority**: P1
- **Effort**: L
- **Risk**: HIGH
- **Depends on**: Plan 009
- **Category**: correctness / reliability / reproducibility
- **Planned at**: commit `1bf7bb8`, 2026-08-15

## Why this matters

The first LoRA experiment still needs trustworthy step semantics, checkpoints,
resume, data isolation, and failure reporting. Today `num_iters` and `max_steps`
are both declared at `src/vocalrender/training/config.py:69-80`; the scheduler
uses `max_steps` while progress/save/loop paths use `num_iters` at
`runners/svs.py:417-425,574,708-800`. Checkpoints load non-strictly and a failed
`latest` update only warns at `checkpoint.py:45-105,258-272`. The signal handler
calls `os._exit(0)` at `runtime.py:183-214`, validation prompt construction can
combine train and validation data at `dataset_ops.py:227-263`, and requested
CUDA may fall back to CPU. These defects can invalidate a single-GPU result.

Multi-rank rendezvous, distributed signal-safe checkpointing, second-signal
behavior, network-filesystem durability proofs, and production cloud preemption
are deliberately deferred to Plan 015B so they do not block the first 4070
evidence.

## Scope

**In scope:** canonical `total_steps`; single-rank staged/hash-verified
checkpoints and `latest`; strict resume compatibility; deterministic RNG/sample
state; immutable run provenance; nonfinite failure; truthful single-rank
interruption status; same-split validation prompts; worst-case prompt budget;
fail-closed device selection; CPU-only synthetic tests and one-GPU smoke hooks.

**Out of scope:** DDP/FSDP signal rendezvous, cross-rank checkpoint-on-signal,
second-signal escalation, network/shared-filesystem atomicity edge cases,
production scheduler integration, real model-quality training, and publishing.

## Implementation

### 1. Establish one canonical step contract

Use one `total_steps` value for scheduler construction, progress conditioning,
logging, loop bounds, validation, checkpoint cadence, completion state, and CLI
display. Legacy configs parse only when `num_iters == max_steps` or one value is
absent and migrates deterministically; mismatches fail before optimizer/model
work. Define zero-based execution `0..total_steps-1` and completed resume state
`next_step == total_steps`.

**Verify:** config tests reject mismatches and a toy run schedules, saves, and
finishes on the same declared last step.

### 2. Make local checkpoint publication verifiable and fail closed

Write a single-rank checkpoint to a contained temporary sibling. Close and
flush required files; use file/parent-directory fsync where the supported local
filesystem exposes it, but do not attempt NFS/GPFS/cloud durability guarantees.
Generate a manifest of relative filenames, sizes, and SHA-256 values; verify the
manifest before renaming the staging directory to its final step name.

Publish `latest` only after verification, preserve the previous verified pointer
until the new checkpoint succeeds, and verify the resolved target afterward.
Pointer failure is fatal to the save. Never recursively remove unresolved,
out-of-root, or user-created directories. Loading verifies containment,
manifest, required adapter/full-model, optimizer, scheduler, RNG, and runtime
files before mutating process state. Expected missing base LoRA keys use an
explicit allowlist; blanket `strict=False` is not acceptance.

**Verify:** corruption/missing-file/pointer-failure tests return nonzero and
leave the previous checkpoint loadable; a valid checkpoint round-trips exactly.

### 3. Capture exact single-GPU resume state and provenance

Add a versioned `training-run/v1` manifest with run ID, parent checkpoint, git
SHA/dirty patch hash, canonical config hash, base checkpoint, tokenizer,
AudioVAE, corpus/split/compiled/preprocessed hashes, packages/device, seed,
precision, and resource budget. Persist Python, NumPy, Torch CPU/CUDA, sampler,
worker, and prompt-selection RNG state, or derive stochastic choices from stable
run/epoch/item keys.

Reject incompatible base/model/data/tokenizer/config fields on resume. Only
nonsemantic output/log locations may differ. Validate
`0 <= next_step <= total_steps`; a resume at `total_steps` is already complete,
not a new successful empty run. Compare uninterrupted N steps with K+resume to
N for identical sample order, LR, loss sequence, and toy weights.

### 4. Fail honestly on interruption and nonfinite training

For the required single-rank path, SIGINT/SIGTERM records `interrupted` and
exits nonzero. It may resume from the last verified periodic checkpoint; it is
not required to create a signal-time checkpoint. Do not claim completion after
`os._exit(0)`. A later Plan 015B supplies coordinated multi-rank safe-boundary
saving.

NaN/Inf loss, gradients required by diagnostics, or optimizer state immediately
transitions the run to `failed`, stops before publishing a new checkpoint, and
returns nonzero. `training_complete` is written only after final checkpoint and
`next_step` verification.

### 5. Enforce split and batching safety

Build validation prompt pools only from the frozen validation split; never
concatenate train audio into validation prompts. Record the prompt policy and
reject forbidden song/session overlap. Account for maximum possible prompt
frames—not average overhead—when proving every realized dynamic batch respects
`max_batch_tokens`.

### 6. Refuse silent CPU fallback

Requested CUDA for preprocessing, training, or full-model inference must fail
before loading/writing when unavailable or insufficient. CPU requires an
explicit test-only/diagnostic opt-in and is recorded as the effective device.

## Test plan

- Config/step tests: legacy migration, mismatch, last-step schedule, resume
  bounds, and completed-resume behavior.
- Checkpoint tests: staging, manifest hashes, strict keys, corrupt/missing files,
  traversal, pointer failure, previous-latest preservation, and final reload.
- Resume tests: uninterrupted versus resumed sample order/RNG/LR/toy weights.
- Failure tests: SIGTERM/SIGINT produce interrupted nonzero state; NaN/Inf cannot
  publish or complete.
- Data/device tests: validation prompt isolation, prompt-token upper bound,
  requested CUDA failure, and explicit CPU-test opt-in.
- No multi-process or distributed preemption test belongs here.

Expected interface:

```powershell
python scripts/verify_training_run.py --run-dir checkpoints/<toy-run> --require-state training_complete
python scripts/verify_checkpoint.py checkpoints/<toy-run>/latest
python -B -m pytest -q -p no:cacheprovider tests/test_training_lifecycle.py tests/test_training_checkpoint.py
python -m black --check src/vocalrender/training src/vocalrender/preprocessing scripts tests
python -m flake8 --max-line-length=120 --extend-ignore=E203 src/vocalrender/training src/vocalrender/preprocessing scripts tests
```

## Done criteria

- [ ] One canonical `total_steps` drives every single-GPU runtime consumer.
- [ ] Staged hash-verified checkpoints and `latest` fail closed and preserve the prior good state.
- [ ] Resume compatibility, RNG/sample order, and final `next_step` are tested.
- [ ] Run provenance is immutable and machine-readable.
- [ ] Interruptions and nonfinite values cannot exit/record success.
- [ ] Validation prompts stay within split and realized batches stay within budget.
- [ ] Requested CUDA never silently falls back to CPU.
- [ ] No Plan 015B distributed/platform work was pulled into this critical path.

## STOP conditions

Stop if compatibility requires accepting mismatched weights/data, a contained
staging/pointer strategy cannot work on the local experiment filesystem, user
checkpoints would be overwritten, single-GPU resume cannot be made exact, or
the requested implementation expands into multi-rank/cloud preemption. Record
the blocker and hand the latter scope to Plan 015B.

## Maintenance notes

This plan is sufficient only for `world_size == 1` on an approved local
filesystem. Any multi-rank, preemptible cloud, shared/network filesystem, or
coordinated signal-time save requires Plan 015B before launch.
