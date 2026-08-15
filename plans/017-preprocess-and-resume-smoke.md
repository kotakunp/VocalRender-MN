# Plan 017: Prove the tiny end-to-end path before full corpus preprocessing

> **Executor instructions**: This is the first plan authorized to create local
> preprocessed artifacts and perform a tiny training smoke, not a pilot or full
> run. Prove dataset → model → LoRA → checkpoint → resume → inference before
> preprocessing the full corpus. Work on `main`; large artifacts remain ignored.
> Subagents do not commit; the primary integrator reviews and pushes with the
> user's configured Git identity and no co-author trailers.
>
> **Drift check (run first)**:
> `git diff --stat 1bf7bb8..HEAD -- conf scripts src/vocalrender data/manifests experiments tests plans`

## Status

- **Status**: TODO
- **Priority**: P1
- **Effort**: XL
- **Risk**: HIGH
- **Depends on**: Plans 011, 014, 015A, 016
- **Category**: integration / preprocessing / training smoke
- **Planned at**: commit `1bf7bb8`, 2026-08-15

## Goal

Prove on a deterministic tiny subset that the approved Mongolian data compiles,
preprocesses, trains LoRA for two steps, resumes exactly to four, and reloads for
inference. Only after that chain passes may the executor spend time/storage on
full approved train/validation preprocessing.

## Scope

**In scope:** accelerator/storage preflight, deterministic tiny train/validation
subset, tiny preprocessing, two-step/resumed-four-step LoRA smoke, adapter load
and bounded inference, optional tiny overfit, then full approved preprocessing,
immutable manifests, and local checkpoint verification.

**Out of scope:** pilot comparison, hyperparameter selection, final test access,
unrestricted training, uploading artifacts, silent quarantine, or preprocessing
the full corpus before the end-to-end smoke passes.

## Execution

### 1. Freeze inputs, tiny subset, and separate output budgets

Require approved corpus/split/compiled hashes from Plans 013–014 plus passing
Plan 011 and Plan 015A/016 verification. Record base checkpoint, tokenizer,
AudioVAE, code/config hashes, devices, workers, output roots, disk/VRAM/wall-time
budgets, and cleanup policy in `experiments/007_preprocess_resume_smoke/config/`.

Create an explicit checked-in tiny-subset manifest; do not rely on a global
`max_samples`, dataset order, or filesystem order. It must contain train and
validation coverage, at least two songs, at least one valid same-song
non-overlapping prompt pair, and no test items. Freeze item IDs and hashes.

Use distinct content-addressed roots such as `data/preprocessed_smoke/<id>` and
`data/preprocessed/<full-id>`; a smoke run must never overwrite or masquerade as
the full dataset.

### 2. Preprocess only the deterministic tiny subset

Run fail-closed preprocessing against the tiny manifest. Require discovered =
written + quarantined accounting, with quarantine zero unless explicitly
preapproved; finite tensors; expected shapes/dtypes; contained paths; and
content-addressed metadata/shard hashes. Requested CUDA must not fall back to
CPU. The current preprocessing CLI accepts a positional config path, so use:

```powershell
python scripts/preprocess_svs_data.py conf/mn_svs_preprocess_smoke.yaml
```

**Gate:** tiny preprocessing exits 0, emits the exact frozen item counts, and
its dataset identity validates. Stop before any full preprocessing on failure.

### 3. Train two steps to a verified LoRA checkpoint

Use a minimal single-GPU LoRA config with `total_steps: 2`, deterministic seed,
the tiny train/validation data, a final-step save, and validation disabled or
tiny/predeclared. The training CLI accepts `--config_path`:

```powershell
python scripts/train_vocalrender_svs.py --config_path conf/mn_svs_train_smoke_2step.yaml
```

Require finite loss/LR/gradient diagnostics, nonempty expected adapter
gradients, unchanged base/non-LoRA tensors, a manifest-valid final checkpoint at
step 1, and `next_step=2`.

### 4. Resume the same run exactly to four steps

Resume the verified checkpoint with unchanged semantic inputs and the one
explicit smoke-only horizon extension to `total_steps: 4`. Require steps 2 and
3 exactly once, restored optimizer/scheduler/RNG/sample order, final checkpoint
at step 3, and `next_step=4`. Compare with an uninterrupted four-step tiny run
where feasible; no new semantic run may masquerade as exact resume.

```powershell
python scripts/train_vocalrender_svs.py --config_path conf/mn_svs_train_smoke_4step_resume.yaml
python scripts/verify_checkpoint.py checkpoints/<smoke-run>/latest
```

### 5. Load the adapter and run bounded inference

Use Plan 016's strict dry-run to verify base fingerprint, LoRA configuration,
expected adapter keys, and positive adapter parameter count. Generate one
bounded ignored WAV from a frozen smoke item and validate format, duration,
finite samples, and checksum. This proves the complete adapter-consumption path;
audio quality is not an acceptance claim.

### 6. Optionally run a predeclared tiny-overfit diagnostic

Only after the four-step resume/inference gate, the operator may authorize at
most 100 steps on one or a few tiny-train items. Success means loss decreases,
the expected LoRA tensors change, and the adapter reloads. Failure blocks Plan
018. Do not extend the cap or inspect final test data.

### 7. Preprocess the full approved train/validation corpus

Only after Steps 2–5 pass (and Step 6 if authorized), run full preprocessing to
the separate full content-addressed root. Require exact source/compiled hashes,
discovered/written/quarantined counts, split/song/singer aggregates, prompt
coverage, finite tensors, shard hashes, and storage budget. The test split
remains frozen and unprocessed for pilot tuning unless Plan 020's final protocol
later authorizes its separate evaluation preprocessing.

```powershell
python scripts/preprocess_svs_data.py conf/mn_svs_preprocess_full.yaml
```

Full preprocessing failure blocks Plan 018 even when the tiny smoke passed.

### 8. Record immutable smoke and full-preprocessing evidence

Store sanitized run records, tiny/full dataset identities, counts/hashes,
commands, timing, peak resources, checkpoint verification, inference metadata,
changed-parameter summary, and explicit status. Keep Arrow data, latents,
checkpoints, full logs, and generated audio outside Git.

## Verification

```powershell
python scripts/check_runtime.py --require-cuda --task preprocess
python scripts/verify_checkpoint.py checkpoints/<smoke-run>/latest
python scripts/infer_vocalrender_svs_single.py --ckpt_dir pretrained_models/VocalRender-Pro --lora_dir checkpoints/<smoke-run>/latest --verify-checkpoint
python -B -m pytest -q -p no:cacheprovider
python -m black --check src/vocalrender scripts tests
python -m flake8 --max-line-length=120 --extend-ignore=E203 src/vocalrender scripts tests
```

The first and third scripts are deliverables of prerequisite Plans 011/016;
verify they exist before execution. Git status must show no staged raw audio,
Arrow/latent shards, checkpoints, or generated WAVs.

## Done criteria

- [ ] Explicit tiny train/validation subset has two songs, valid prompts, and no test data.
- [ ] Tiny preprocessing has exact balanced counts and a frozen identity.
- [ ] Two-step run ends at `next_step=2` with finite values and verified LoRA.
- [ ] Resume executes only steps 2–3 and ends at `next_step=4` with restored state.
- [ ] Plan 016 loads the adapter and one bounded inference WAV validates.
- [ ] Optional overfit, if authorized, stays within 100 steps and is reported.
- [ ] Only after the smoke, full approved preprocessing completes with exact hashes/counts.
- [ ] Full preprocessing passes before Plan 018; large/private artifacts remain uncommitted.

## STOP conditions

Stop on input-hash drift, non-deterministic tiny selection, silent quarantine,
CUDA fallback, nonfinite values, missing adapter gradient, non-LoRA mutation,
checkpoint/latest mismatch, resume divergence, adapter-load/inference failure,
test-split access, full preprocessing before smoke success, or resource overrun.
Fix the owning plan instead of increasing data size or training steps.

## Maintenance notes

Smoke and full preprocessing are distinct immutable dataset identities. A smoke
success proves plumbing only; pilots remain blocked until the subsequent full
approved preprocessing manifest also passes.
