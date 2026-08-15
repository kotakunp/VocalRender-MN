# Plan 015B: Harden distributed checkpointing and production preemption

> **Executor instructions**: This is a conditional production-hardening plan,
> not a prerequisite for the first single-GPU 4070 experiment. Execute it before
> any run with `world_size > 1`, coordinated FSDP/DDP checkpointing,
> preemptible-cloud scheduling, or a shared/network filesystem. Work on `main`;
> subagents do not commit, and the primary integrator owns review, tests, commit,
> and push with the user's Git identity and no co-author trailers.
>
> **Drift check (run first)**:
> `git diff --stat 1bf7bb8..HEAD -- src/vocalrender/training scripts conf tests docs`

## Status

- **Status**: TODO
- **Activation**: conditional; not on the first local single-GPU critical path
- **Priority**: P2
- **Effort**: L
- **Risk**: HIGH
- **Depends on**: Plan 015A
- **Category**: distributed reliability / production operations
- **Planned at**: commit `1bf7bb8`, 2026-08-15

## Why this matters

The current signal handler exits each process through `os._exit(0)` while the
checkpoint path can perform cross-rank gathers and barriers. In a multi-rank or
preemptible job, one rank can exit while peers remain in collectives, producing
hangs, lost progress, ambiguous status, or partial shared-storage state. These
risks are real for serious cloud/distributed training but are unnecessary scope
for the first single-rank adaptation proof.

## Scope

**In scope:** coordinated signal state, rank rendezvous at a safe optimizer
boundary, rank-failure propagation, main-rank publication, FSDP/DDP state
gathers, second-signal/timeout policy, scheduler preemption integration,
network/shared-filesystem durability strategy, distributed resume tests, and
operator runbook.

**Out of scope:** model quality, hyperparameter tuning, data acquisition,
single-GPU correctness already owned by Plan 015A, and automatic cloud provider
deployment.

## Steps

### 1. Declare supported deployment profiles

Document/test the exact combinations of backend, world size, checkpoint
filesystem, scheduler signal, grace period, and durability guarantees. Fail
preflight for untested combinations instead of assuming local rename/fsync
semantics apply to NFS, GPFS, object mounts, or another shared store.

### 2. Coordinate preemption outside the signal handler

The handler sets a minimal process-local flag. At the next declared safe
optimizer boundary, propagate the stop request, rendezvous all healthy ranks,
gather state once, publish through Plan 015A's verified manifest contract, mark
`interrupted`, and exit with the documented non-success status. No complex I/O
or collective occurs inside the handler.

Define second-signal and grace-timeout behavior explicitly: force termination,
retain the last verified checkpoint, and mark the next launch/run record
`unclean_interruption`. Never claim a newly partial checkpoint.

### 3. Make distributed publication and failure atomic at the protocol level

Only main rank publishes metadata/`latest`; all ranks verify the same step and
manifest identity. A gather, rank, storage, or pointer failure aborts publication
and preserves the previous verified checkpoint. Implement filesystem-specific
staging/rename/fsync or generation-pointer semantics only for declared supported
profiles.

### 4. Prove distributed resume and scheduler behavior

Use tiny deterministic two-rank CPU/Gloo fixtures for state-machine behavior
and an opt-in GPU/FSDP smoke for actual collectives. Test preemption during
forward, backward, optimizer boundary, state gather, file publication, and
pointer update. Compare resumed sample/LR/weight state with uninterrupted runs.

### 5. Publish an operator runbook

Document signals, grace periods, latest-good recovery, stale staging cleanup,
storage budgets, retry rules, and how to distinguish interrupted, failed, and
completed jobs. Cleanup must resolve/contain every target and never delete a
verified permanent checkpoint automatically.

## Verification

```powershell
python -B -m pytest -q -p no:cacheprovider tests/test_distributed_preemption.py tests/test_distributed_checkpoint.py
python scripts/check_runtime.py --task distributed-train --config <selected-run-config>
```

Expected: every injected rank/storage/signal failure either resumes from a
verified checkpoint or returns a truthful failed/interrupted state; no scenario
publishes partial `latest` or exits success.

## Done criteria

- [ ] Supported backend/filesystem/scheduler profiles are explicit and fail closed.
- [ ] All ranks coordinate stop/save/exit without signal-handler collectives.
- [ ] Second-signal and timeout behavior preserve the previous verified checkpoint.
- [ ] Distributed publication cannot expose a partial checkpoint.
- [ ] Two-rank resume and injected-failure tests pass.
- [ ] Operator recovery/cleanup procedures are documented and bounded.

## STOP conditions

Stop if the target distributed/filesystem profile cannot provide the declared
durability primitive, rank failures cannot propagate reliably, tests require
real production data/weights, or implementation would weaken Plan 015A's
single-rank contract. Do not mark the profile supported without an opt-in
integration result on equivalent infrastructure.

## Maintenance notes

Plan 015B is conditionally required before Plan 019 whenever the frozen
`selected-run.yaml` uses multiple ranks, preemptible scheduling, or a
shared/network checkpoint filesystem. It is not a dependency for a local
single-GPU 4070 run.
