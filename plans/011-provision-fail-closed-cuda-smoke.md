# Plan 011: Provision a fail-closed CUDA environment and close the upstream smoke

> **Executor instructions**: Work directly on `main`. This is a bounded
> infrastructure gate, not authorization to train or to rewrite model code.
> Subagents do not commit. The primary integrator owns review, tests, commit,
> and push using the user's configured Git identity without co-author trailers.
>
> **Drift check (run first)**:
> `git diff --stat 1bf7bb8..HEAD -- scripts conf experiments tests pyproject.toml README.md`

## Status

- **Status**: DONE
- **Priority**: P1
- **Effort**: M
- **Risk**: MEDIUM
- **Depends on**: Plan 009
- **Category**: infrastructure / reproducibility
- **Planned at**: commit `1bf7bb8`, 2026-08-15

## Why this matters

Experiment 001 is blocked because the current bundled PyTorch is CPU-only,
while `scripts/infer_vocalrender_svs_single.py` loads the roughly 9.5 GB local
VocalRender-Pro checkpoint and defaults to CUDA. Several inference and
preprocessing paths can fall back to CPU, which can turn an invalid accelerator
setup into a long, misleading run. The project needs one explicit hardware
preflight and an immutable successful or blocked smoke record before native
study synthesis or training.

## Scope

**In scope:** read-only GPU/storage/runtime probe, explicit device policy,
bounded upstream Chinese smoke, WAV validation, sanitized immutable run record,
and documentation.

**Out of scope:** driver installation by automation, dependency upgrades not
required by the lock/config, downloads, model changes, Mongolian quality claims,
and any preprocessing or training.

## Steps

### 1. Add a reusable accelerator preflight

Create a CLI/module that reports Python, PyTorch, CUDA build/runtime, visible
devices, compute capability, free/total VRAM, free workspace/checkpoint space,
and requested dtype. `--require-cuda` must exit nonzero when CUDA is unavailable;
CPU use requires an explicit `--allow-cpu` flag and is forbidden for this smoke.
Sanitize machine usernames and home paths from persisted reports.

Set documented minimums from measured model loading plus safety margin, not a
guessed universal GPU claim. Distinguish `blocked_environment` from
`failed_inference`.

**Verify:** unit tests mock no-GPU, insufficient-VRAM/storage, and valid-GPU
states; the current CPU-only environment fails quickly and clearly.

### 2. Provision externally, then capture a frozen environment

The operator supplies a supported NVIDIA host. Install the project using its
declared Python range and a CUDA-compatible PyTorch build, then record package
versions and config/tokenizer hashes. Never persist tokens or absolute home
paths. Do not alter the local checkpoint.

**Verify:** `torch.cuda.is_available()` is true, the selected device matches the
run record, and the preflight exits 0 before weights are loaded.

### 3. Run one bounded upstream regression smoke

Use the bundled Chinese demo item and prompt with
`pretrained_models/VocalRender-Pro`; allow one normal attempt and one retry only
for a simple environment correction. Require prompt audio, deterministic seed
where supported, an ignored output path, exit code 0, and a nonempty 48 kHz WAV
whose checksum/duration are recorded.

Do not claim success from model load alone. A CUDA out-of-memory error is a
blocked capacity result, not permission to fall back silently to CPU.

### 4. Append, never rewrite, Experiment 001 evidence

Add a timestamped run record under `experiments/001_upstream_smoke_test/results/`
and update its index pointer. Preserve the prior CPU-blocked record. Include git
SHA, command template, environment fingerprint, input/output hashes, elapsed
time, status, and sanitized error category. Generated audio stays ignored.

## Verification commands

```powershell
python scripts/check_runtime.py --require-cuda --task inference --json-out outputs/runtime-preflight.json
python scripts/infer_vocalrender_svs_single.py --ckpt_dir pretrained_models/VocalRender-Pro --json_file examples/opencpop_demo.json --item_name 2003000087 --prompt_audio examples/prompt_audio/2003000081.wav --output outputs/upstream-smoke.wav
python -m pytest -q
```

Also run Black and flake8 on touched Python files and validate the output WAV's
sample rate, channels, duration, finite samples, peak, and SHA-256.

## Done criteria

- [x] CUDA/device/storage failures are detected before model load.
- [x] A real upstream demo produces a validated 48 kHz WAV on CUDA.
- [x] Experiment 001 retains both the old blocker and new immutable run record.
- [x] No CPU fallback, download, checkpoint change, raw audio commit, or secret occurs.
- [x] Existing tests plus new preflight tests pass.

## STOP conditions

Stop and record `blocked` if no approved CUDA host exists, VRAM/storage remains
insufficient, provisioning needs driver/admin changes not authorized by the
operator, weights are incomplete, or two bounded attempts fail. Do not patch
neural architecture or start Plan 012 synthesis on an unverified runtime.

## Maintenance notes

Re-run preflight whenever host, driver, PyTorch, checkpoint, or precision
changes. Every run record is append-only and names artifacts by relative path
and hash.
