# Plan 009: Run and document reproducible Milestone 0 experiments

> **Executor instructions**: This plan integrates prior work and records actual
> environment-dependent results. Do not start training, download data, or spend
> unbounded time debugging CUDA. A documented blocked inference result is valid
> if frontend/data gates pass. Run each verification gate and update this
> plan's row in `plans/README.md` when done.
>
> **Drift check (run first)**:
> `git diff --stat c0ab96e..HEAD -- experiments reports README.md examples scripts/mn src/khalkha_frontend tests`
> Confirm Plans 004-008 are `DONE`. Reconcile any existing experiment files
> rather than overwriting notes/results.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: `plans/004-add-morphology-and-context-mining.md`,
  `plans/005-canonicalize-phonetic-benchmark.md`,
  `plans/006-scaffold-evidence-gated-phonology.md`,
  `plans/007-build-tokenizer-audit.md`,
  `plans/008-add-vocalrender-score-adapter.md`
- **Category**: docs / direction
- **Planned at**: commit `c0ab96e`, 2026-08-15

## Why this matters

Milestone 0 succeeds when the upstream engine is preserved, research inputs are
traceable, frontend uncertainty is explicit, and the next pronunciation
experiment is reproducible. This plan runs cheap gates, attempts one bounded
upstream smoke inference using the already-present checkpoint, records why it
is blocked if necessary, and produces a final report that chooses the next
experiment based on tokenizer/benchmark evidence rather than speculation.

## Current state

- Upstream README's tested demo command is:

  ```bash
  python scripts/infer_vocalrender_svs_single.py \
    --ckpt_dir pretrained_models/VocalRender \
    --json_file examples/opencpop_demo.json \
    --item_name 2003000087 \
    --prompt_audio examples/prompt_audio/2003000081.wav \
    --output outputs/demo_2003000087.wav
  ```

- This workspace instead has `pretrained_models/VocalRender-Pro/`, including
  model/tokenizer/AudioVAE files, so the same script can target that checkpoint.
- The released checkpoint requires prompt audio; bundled prompt clips exist.
- The planning shell had no `python`/`uv` on PATH. The executor must provision a
  supported environment and record it.
- `scripts/infer_vocalrender_svs_single.py` defaults to CUDA and loads ~9.5 GB
  model weights. No CPU success is promised.
- The source prompt explicitly says not to spend the whole milestone debugging
  CUDA: record the blocker and continue.
- Plans 004 and 007 create documentation/results for experiments 002 and 003;
  reconcile rather than recreate them.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Unit gate | `python -m pytest -q` | all tests pass |
| Formatting | `python -m black --check src/khalkha_frontend scripts/mn tests` | exit 0 |
| Lint | `python -m flake8 src/khalkha_frontend scripts/mn tests` | exit 0 |
| Benchmark gate | `python scripts/mn/validate_benchmark.py benchmarks/MN-PHON-250/manifest.yaml` | 250 valid items |
| Tokenizer gate | Plan 007's real audit command | exit 0; reports current |
| Adapter gate | Plan 008's example conversion command | exit 0; score valid |
| GPU probe | `python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO_CUDA')"` | records environment; CUDA may be false |

## Scope

**In scope:**

- `experiments/README.md`
- `experiments/001_upstream_smoke_test/README.md`
- `experiments/001_upstream_smoke_test/config/run.yaml`
- `experiments/001_upstream_smoke_test/results/run.json`
- existing `experiments/002_tokenizer_audit/**` result/doc updates from an actual
  run
- existing `experiments/003_phonetic_benchmark/**` result/doc updates from an
  actual mining/validation run
- `experiments/004_frontend_baseline/README.md`
- `experiments/004_frontend_baseline/config/score.json`
- `experiments/004_frontend_baseline/results/run.json`
- `experiments/005_vocalrender_mn_lora/README.md` containing prerequisites only,
  not a training config/launch
- `reports/milestone-0.md`
- `README.md` only for a concise pointer to the frontend, benchmark, provenance,
  and report
- generated smoke audio under ignored `outputs/` (local only; do not commit)

**Out of scope:**

- Training/fine-tuning/LoRA launch, preprocessing speech as SVS training data,
  AudioVAE changes, or new downloads.
- Generating Music3 audio or calling external TTS services.
- Collecting native-speaker ratings.
- Modifying source code to make an environment-specific inference failure pass.
- Committing generated audio, checkpoints, caches, or absolute machine paths.

## Git workflow

- Branch: `main` (work directly; do not create a task branch)
- Suggested commits:
  `docs: record Milestone 0 experiments` and
  `docs: publish VocalRender-MN foundation report`.
- Do not push/open a PR unless instructed.

## Steps

### Step 1: Create the experiment contract

Create `experiments/README.md` defining required files for numbered
experiments:

- `README.md`: question, hypothesis, inputs, command, interpretation limits;
- `config/`: checked-in deterministic inputs/config;
- `results/run.json`: schema-versioned machine result with status
  `success|blocked|failed`, command, git SHA, timestamps, environment summary,
  input hashes, output metadata/checksum, warnings, and blocker;
- output audio/model artifacts remain under ignored paths and are referenced by
  relative path/hash only;
- `notes` belong in README/run record, not directory prefixes.

Define sanitization: no absolute home paths, secrets, machine usernames, raw
speaker identifiers, or service tokens.

**Verify**: every experiment directory 001-005 has a README and documented
config/results policy; YAML/JSON files parse.

### Step 2: Run all cheap deterministic gates first

Record git SHA, Python/platform/package versions, and input manifest hashes.
Run:

1. full pytest;
2. Black and flake8 checks;
3. benchmark validator;
4. tokenizer audit;
5. context-mining configured sample;
6. frontend score conversion and adapter/upstream-helper regression.

Write run records for experiments 002-004 using actual counts/statuses. Do not
copy claimed values from plan text. If a gate fails, mark the relevant
experiment failed and stop before model inference until the deterministic issue
is fixed by the owning plan/executor.

**Verify**: all six gates exit 0 and run JSON schemas parse.

### Step 3: Attempt one bounded upstream VocalRender-Pro smoke inference

Before inference, record:

- checkpoint directory and hashes/sizes for config/tokenizer (not the entire
  9.5 GB weight unless already available cheaply);
- input example/item and prompt-audio checksum/duration;
- Python, PyTorch, CUDA runtime, GPU model and memory if available;
- exact output path under `outputs/`.

Use a bundled upstream Chinese demo pair first, because it isolates upstream
functionality from Mongolian frontend quality. Adapt the README command only by
setting `--ckpt_dir pretrained_models/VocalRender-Pro` and an ignored output
path. Apply a bounded operational budget: one normal attempt and at most one
retry for a straightforward environment/config correction.

Outcomes:

- **success**: record exit code, elapsed time, output WAV path/hash, sample rate,
  channels, duration, and nonzero file size; do not commit audio;
- **blocked**: record exact missing Python/CUDA/dependency/VRAM condition and
  remediation suggestion; do not modify model code or start lengthy debugging;
- **failed**: record reproducible command and concise error class without
  copying secrets/absolute home paths.

**Verify on success**:
`python -c "import soundfile as sf; x,sr=sf.read('outputs/<file>.wav'); assert len(x)>0 and sr==48000; print(sr,len(x))"`
-> exit 0, 48 kHz nonempty audio.

### Step 4: Run the frontend baseline without claiming native pronunciation

Use Plan 008's checked-in Mongolian score input to produce an upstream JSON
entry and build the prompt/tokenization audit. If upstream smoke inference
succeeded and resources permit, optionally render **one** baseline Mongolian
sample with a bundled clean prompt, clearly labeled as exploratory and not a
native-quality result.

Do not fill expected phones or benchmark ratings from this output. Record:

- exact score fields and melisma mapping;
- normalization issues/unresolved pronunciation count;
- tokenizer metrics;
- whether inference ran and output metadata;
- listening/native evaluation as `not_performed` unless actually performed by
  an identified protocol.

**Verify**: score adapter validation passes and any optional output is ignored,
nonempty, and recorded without being committed.

### Step 5: Write a prerequisites-only LoRA experiment placeholder

In `experiments/005_vocalrender_mn_lora/README.md`, state that training is
blocked until all of these are true:

- licensed/consented native Mongolian singing data with score alignment;
- benchmark evidence for high-risk contexts;
- tokenizer/input strategy decision from controlled experiments;
- defined train/validation split avoiding singer/song leakage;
- synthetic Music3 filtering policy based on GREEN/YELLOW/RED evidence;
- upstream regression/rehearsal strategy;
- resource/training-use manifest approvals;
- GPU/storage budget and rollback/evaluation criteria.

Do not add a launchable training config, LoRA hyperparameters, or command yet;
that would create false readiness.

**Verify**: no training process is running and no new files exist under
`checkpoints/`, `runs/`, or preprocessed data paths.

### Step 6: Produce the Milestone 0 report and exact next experiment

Create `reports/milestone-0.md` with evidence-backed sections:

1. implemented plans/commits and verification commands/results;
2. exact data/resources found, semantic paths, counts, and provenance/use
   status;
3. missing data/evidence and unresolved licenses;
4. upstream smoke outcome and blocker if any;
5. tokenizer audit findings without conflating fragmentation with
   pronunciation;
6. benchmark status (250 items, audio/rating coverage, unresolved fields);
7. frontend capabilities and explicit non-capabilities;
8. evidence required before adding syllabification/G2P/allophone rules;
9. exact next experiment.

Recommended next experiment, unless actual evidence contradicts it:

> Record or curate native Standard Khalkha speech references for a balanced
> subset of MN-PHON-250 covering Л/Г/Х/soft-sign contexts, run the same fixed
> score through raw-Cyrillic VocalRender-Pro and (where available) three Music3
> takes, collect blinded native-speaker 0/1/2 judgments, and use only recurring
> errors with linked evidence to propose the first narrow override/allophone
> rules.

Specify a bounded sample size from actual benchmark groups, selection seed,
audio metadata schema, rater protocol, success criteria, and STOP conditions.
Do not recommend LoRA as the immediate next experiment unless native annotated
singing data and licensing are already present.

**Verify**:

- every factual count links to a command/report/manifest;
- `rg -n "__GET__|__MAKE__" experiments reports README.md` -> no matches;
- README retains upstream quick-start content and only adds pointers.

## Test plan

- Ordinary unit tests remain the main code gate.
- Parse every checked-in experiment YAML/JSON in a test or validation command.
- On successful inference, inspect output audio metadata; do not use subjective
  listening as an automated pass condition.
- On blocked inference, validate that the run record contains a nonempty blocker
  and no claimed output.
- Scan committed experiment/report files for absolute user paths and marker
  directories.

## Done criteria

- [ ] All deterministic gates pass and their real results are recorded.
- [ ] Upstream smoke is either successful with validated 48 kHz output or
  explicitly `blocked` with an exact environment reason.
- [ ] No raw/generated audio or checkpoint artifact is committed.
- [ ] Frontend baseline preserves explicit score/melisma and unresolved
  pronunciation.
- [ ] LoRA experiment remains prerequisites-only; no training launched.
- [ ] `reports/milestone-0.md` states found/missing data, evidence requirements,
  and one exact bounded next experiment.
- [ ] No permanent path in experiments/reports uses `__GET__` or `__MAKE__`.
- [ ] `plans/README.md` marks Plan 009 `DONE` (or `BLOCKED` only if a required
  deterministic, non-GPU gate cannot complete).

## STOP conditions

Stop and report if:

- any prerequisite plan is not done or deterministic tests fail;
- running inference would download missing weights/data or require modifying
  upstream code;
- two bounded smoke attempts fail for environment/CUDA reasons;
- a report claim cannot be traced to current output/manifest evidence;
- the next experiment would require external recordings, service calls, or
  licensing approval not authorized by the operator;
- any command starts training, preprocessing of a large corpus, or bulk Music3
  generation.

## Maintenance notes

- Experiment run records are immutable evidence; append a new run rather than
  rewriting a past outcome when conditions change.
- Keep project README concise and upstream-friendly; detailed Mongolian research
  state belongs in reports/experiments.
- Reviewers should distinguish `blocked` infrastructure from failed research
  hypotheses and should reject subjective pronunciation claims without the
  documented native-evaluation protocol.
