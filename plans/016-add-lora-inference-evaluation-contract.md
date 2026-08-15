# Plan 016: Add usable LoRA inference and a complete evaluation contract

> **Executor instructions**: Build adapter loading and strict evaluation using
> toy checkpoints first. Work on `main`; do not run a pilot or publish weights.
> Subagents do not commit. The primary integrator reviews all loading semantics,
> tests, commits, and pushes with the user's Git identity and no co-author trailers.
>
> **Drift check (run first)**:
> `git diff --stat 1bf7bb8..HEAD -- scripts/infer_vocalrender_svs.py scripts/infer_vocalrender_svs_single.py src/vocalrender/model src/vocalrender/evaluation src/vocalrender/training tests conf`

## Status

- **Status**: TODO
- **Priority**: P1
- **Effort**: L
- **Risk**: HIGH
- **Depends on**: Plans 011, 015A
- **Category**: inference / evaluation correctness
- **Planned at**: commit `1bf7bb8`, 2026-08-15

## Why this matters

Training already constructs LoRA through `runners/svs.py:205-208`, freezes
non-LoRA parameters in `model/voxcpm2.py:1560-1567`, and saves adapter-only
weights/config in `training/checkpoint.py:196-213`. But both public inference
scripts instantiate with `lora_config=None`
(`infer_vocalrender_svs_single.py:100-117`, `infer_vocalrender_svs.py:807-836`)
and load with `strict=False`. A successful LoRA training run therefore does not
yet yield an unambiguously usable inference artifact. Evaluation also catches
generation/metric errors, and SingMOS can call `torch.hub.load(...,
trust_repo=True)` at `evaluation/metrics.py:88-93`, allowing partial or
environment-dependent reports.

## Scope

**In scope:** explicit base-plus-adapter CLI/API, adapter manifest/fingerprint
checks, strict key loading, legacy full-checkpoint preservation, offline/pinned
metric policy, complete-count evaluation manifests, comparison command, tests,
and lifecycle integration.

**Out of scope:** training, merging adapters into base weights, model upload,
new learned metrics, architecture changes, or accepting a partial evaluation.

## Steps

### 1. Define unambiguous checkpoint arguments

Support this semantic contract in single and batch inference:

```powershell
python scripts/infer_vocalrender_svs_single.py --ckpt_dir pretrained_models/VocalRender-Pro --lora_dir checkpoints/<run>/latest ...
```

`--ckpt_dir` is always the complete base checkpoint. `--lora_dir` is optional
and must contain adapter config, weights, and Plan 015A manifest. Preserve the
existing full-checkpoint-only path. Reject a directory that ambiguously mixes
base and adapter layouts.

### 2. Verify and load the adapter strictly

Before model construction, verify schema, file hashes, base config/tokenizer/
AudioVAE/checkpoint fingerprints, architecture, target modules, rank/alpha/
dropout, dtype compatibility, and completed checkpoint state. Instantiate with
the saved LoRA config, load base weights under the existing documented contract,
then load only the exact expected adapter keys. Missing, extra, shape-mismatched,
zero-sized, or non-LoRA keys are fatal.

Expose a dry-run `--verify-checkpoint` mode that does not generate audio and
prints sanitized fingerprints and adapter parameter count. Never mutate or
merge the base checkpoint.

### 3. Make evaluation complete or failed

Every evaluation manifest predeclares expected item/source/seed/metric counts.
Generation or required metric failure yields nonzero status and
`evaluation_failed`; it cannot produce an apparently complete summary from a
subset. Optional metrics are explicitly optional before the run and report
coverage separately.

Pin metric implementation/version/weight checksums and require local approved
weights for release-gating evaluation. Disable surprise network execution and
`trust_repo` downloads in offline/reproducible mode. Record backend, device,
versions, input/output hashes, failures, and counts.

### 4. Add matched comparison outputs

Provide a command that evaluates base and adapter against the same immutable
item/order/prompt/seed manifest and writes per-item paired records. It must not
select thresholds or tune on final test data. Human ratings stay external to
automatic metrics but join through blind take IDs.

### 5. Wire lifecycle states

A verified final adapter may transition a run from `training_complete` to
`checkpoint_published` (local publication, not internet upload). Only a complete
evaluation can set `evaluation_complete`; only Plan 020's frozen acceptance can
set `release_approved`.

## Test plan

- Tiny modules/checkpoints test correct LoRA load and output difference, bad
  base fingerprint, wrong rank/shape, missing/extra/non-LoRA keys, corrupt hash,
  incomplete checkpoint, and legacy full-checkpoint inference.
- Evaluation fixtures test one failed generation, one missing required metric,
  optional metric absence, count mismatch, offline metric loading, and matched
  base/adapter ordering.
- Run full pytest, Black, flake8, and CLI `--help`/dry-run tests without loading
  the real 9.5 GB model.

Expected verification interface after implementation:

```powershell
python scripts/infer_vocalrender_svs_single.py --ckpt_dir pretrained_models/VocalRender-Pro --lora_dir checkpoints/<run>/latest --verify-checkpoint
python scripts/evaluate_vocalrender_svs.py --config experiments/<evaluation>/config/evaluation.yaml --require-complete --offline
python -m pytest -q tests/test_lora_inference.py tests/test_evaluation_contract.py
```

The dry run reports a positive adapter-parameter count and matching base
fingerprint; evaluation exits nonzero if actual and expected counts differ.

## Done criteria

- [ ] Saved LoRA checkpoints are directly usable with an explicit base path.
- [ ] Base fingerprint and exact adapter keys are verified before inference.
- [ ] Existing full-checkpoint inference remains compatible.
- [ ] Partial generation/required metrics fail the evaluation.
- [ ] Release-gating metrics are pinned/local and lifecycle states remain distinct.

## STOP conditions

Stop if the base checkpoint cannot be fingerprinted without rewriting it, old
CLI semantics become ambiguous, adapter target modules cannot be reconstructed,
or a metric license/weight checksum is unknown. Do not relax strictness to make
an incompatible checkpoint load.

## Maintenance notes

Adapter manifests bind permanently to a base fingerprint. A future merge/export
format requires its own plan and equivalence tests.
