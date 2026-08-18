# VocalRender-MN implementation plans

Generated with the `improve` skill. Plans 001–009 established Milestone 0. The
continuation through training closure was surveyed and planned on 2026-08-15 at
commit `1bf7bb8` after integration validation and parallel read-only audits of
data/evaluation, training/runtime, and preprocessing/LoRA paths.

Each executor must read its plan fully, run its drift check first, honor every
STOP condition, and update the status here. Plans are self-contained execution
contracts; do not infer authorization from a later plan before its dependencies
are done.

## Repository workflow

- Implement directly on `main`; do not create task branches or persistent task
  worktrees.
- Preserve unrelated user changes. Never reset or clean the shared tree.
- Parallel subagents may implement or validate separate scopes but do not
  commit. The primary integrator reviews and resolves all shared-tree work.
- Commits and pushes use the repository user's configured Git/GitHub identity.
  Do not add Codex, Luna, bot, co-author, or generated-by trailers.
- Large/private artifacts remain local and ignored. Check in only code, config,
  schemas, sanitized manifests/hashes/aggregates, tests, and reports.

## Execution order and status

| Plan | Title | Priority | Effort | Depends on | Status |
|---|---|---:|---:|---|---|
| [001](001-establish-verification-baseline.md) | Establish a deterministic Milestone 0 verification baseline | P1 | M | — | DONE |
| [002](002-normalize-layout-and-provenance.md) | Normalize permanent data/resource paths and record provenance | P1 | M | 001 | DONE |
| [003](003-create-frontend-foundation.md) | Create the independent Khalkha frontend foundation | P1 | M | 001, 002 | DONE |
| [004](004-add-morphology-and-context-mining.md) | Add UniMorph access and orthographic-context mining | P1 | M | 002, 003 | DONE |
| [005](005-canonicalize-phonetic-benchmark.md) | Canonicalize MN-PHON-250 and its manual evaluation metadata | P1 | L | 002, 003 | DONE |
| [006](006-scaffold-evidence-gated-phonology.md) | Scaffold evidence-gated syllabification, G2P, and allophones | P1 | L | 003, 005 | DONE |
| [007](007-build-tokenizer-audit.md) | Build a read-only Mongolian tokenizer audit | P1 | M | 003, 004, 005 | DONE |
| [008](008-add-vocalrender-score-adapter.md) | Add a score-preserving VocalRender adapter | P1 | M | 003, 006 | DONE |
| [009](009-run-reproducible-milestone-experiments.md) | Run and document reproducible Milestone 0 experiments | P2 | M | 004–008 | DONE |
| [010](010-build-native-reference-study-kit.md) | Build the deterministic context-stratified 32-item native-reference study kit | P1 | L | 009 | DONE |
| [011](011-provision-fail-closed-cuda-smoke.md) | Provision a fail-closed CUDA environment and close the upstream smoke | P1 | M | 009 | BLOCKED: no CUDA runtime/device |
| [012](012-execute-native-reference-study.md) | Execute the 32-item same-score native-singing study | P1 | XL | 010, 011 | BLOCKED: singer/recordings/raters |
| [013](013-establish-training-corpus-contract.md) | Establish the training-corpus eligibility and leakage-safe split contract | P1 | L | 009 | DONE |
| [014](014-compile-score-aligned-mongolian-svs.md) | Compile and validate score-aligned Mongolian SVS annotations | P1 | XL | 012, 013 | BLOCKED: approved singing corpus missing |
| [015A](015-harden-training-lifecycle.md) | Harden the required single-GPU training lifecycle | P1 | L | 009 | BLOCKED: one-GPU validation unavailable |
| [015B](015b-harden-distributed-preemption.md) | Harden distributed checkpointing and production preemption | P2 | L | 015A | TODO |
| [016](016-add-lora-inference-evaluation-contract.md) | Add usable LoRA inference and a complete evaluation contract | P1 | L | 011, 015A | TODO |
| [017](017-preprocess-and-resume-smoke.md) | Prove the tiny end-to-end path before full corpus preprocessing | P1 | XL | 011, 014, 015A, 016 | TODO |
| [018](018-run-bounded-lora-pilots.md) | Run bounded LoRA pilots and freeze the full-run decision | P1 | XL | 012, 017 | TODO |
| [019](019-run-selected-full-lora-training.md) | Run the selected full LoRA adaptation to its declared horizon | P1 | XL | 018; 015B conditional | TODO |
| [020](020-evaluate-and-close-training.md) | Evaluate the final adapter and close training with an acceptance report | P1 | XL | 019 | TODO |

Status values: `TODO`, `IN PROGRESS`, `DONE`, `BLOCKED: <reason>`, or
`REJECTED: <reason>`.

## Dependency graph

```text
Milestone 0: 001 ──> ... ──> 009 (DONE)

009 ──> 010 study kit ──────────────┐
 ├───> 011 CUDA smoke ──────────────┼──> 012 same-score sung study ──┐
 ├───> 013 corpus rights/splits ────────────────────────────┼──> 014 annotations ─┐
 └───> 015A single-GPU lifecycle ───┐                     │                    │
                                    ├──> 016 LoRA inference/evaluation ────────┤
                         011 ────────┘                                           │
                                                                                v
                              011 + 014 + 015A + 016 ──> 017 tiny E2E, then full preprocess
                              012 + 017 ──────────────> 018 bounded pilots
                                                           │
                                                           v
                                                   019 selected full run
                                                           │
                                                           v
                                                   020 final acceptance

015A ──> 015B distributed/preemption hardening
          └─ conditional gate before 019 only for multi-rank, preemptible cloud,
             or shared/network-filesystem execution
```

Plans 010, 011, 013, and 015A can begin in parallel. Human/data-dependent work
then gates the computational sequence. Plan 019 is not ready merely because a
GPU exists: it requires approved singing data, a resume-tested pipeline, a
passing pilot, and frozen selection/acceptance files. Plan 015B is deliberately
off the first local single-4070 critical path; it becomes mandatory when the
selected run uses multiple ranks, preemptible scheduling, or shared/network storage.

## What “finished” means

The lifecycle has intentionally separate states:

1. `training_complete`: the selected horizon ran and its final checkpoint is valid.
2. `checkpoint_published`: the adapter is locally loadable against the frozen base.
3. `evaluation_complete`: every frozen human/automatic evaluation record exists.
4. `release_approved`: the candidate passed predeclared acceptance predicates.

Plan 020 closes this roadmap even if the candidate is rejected. In that case the
truthful result is “training run complete, candidate rejected,” and any further
tuning requires a new Plan 021. External upload/publication always requires
separate authorization.

## Permanent project layout

```text
resources/
├── unimorph_khk/
├── lexicon/
└── phonology/

data/raw/
├── speech/
├── benchmark_tts/
├── native_speech/
├── native_singing/
└── music3/
```

Provenance, licensing, consent/use status, checksums, and acquisition notes live
in `DATA_SOURCES.md` and versioned manifests. Large contents under `data/`,
`checkpoints/`, `outputs/`, and `pretrained_models/` remain local and ignored;
plans may narrowly re-include small sanitized metadata under `data/manifests/`.

## Repository facts verified for this continuation

- Branch and remote were synchronized on `main` at `1bf7bb8` before planning.
- Baseline validation: 130 pytest tests pass; Black reports 33 unchanged files;
  flake8 passes with line length 120 and `E203` ignored. PyTorch emits two
  deprecation warnings but no test failures.
- CI covers Python 3.10 and 3.11 with pytest, Black, and flake8.
- The bundled local PyTorch is CPU-only; Plan 011 needs an external approved CUDA host.
- `pretrained_models/VocalRender-Pro/` exists locally and is ignored; it is a
  VoxCPM2-family checkpoint of roughly 9.5 GB. The configured training base path
  `pretrained_models/VoxCPM2` is not provisioned.
- No approved Mongolian native-singing training corpus, compiled annotation set,
  or preprocessed training dataset exists yet.
- `data/raw/manifest.yaml` records native and synthetic source permissions as
  unknown; unknown-rights material is not training-eligible.
- MN-PHON-250 exists, but its audio/evaluation manifests and phonology evidence
  registry are empty. The immediate study is 32 items, not all 250.
- Plan 012 cannot be completed by software alone: it requires a real native
  Standard Khalkha singer, explicit evaluation consent, 32 score-matched sung
  recordings, and three completing independent native raters.
- Existing training config has conflicting `num_iters`/`max_steps` consumers;
  checkpoint pointer failures can be warnings; signal exit can skip a save and
  return success; resume provenance/RNG compatibility is incomplete.
- Training can save LoRA-only weights/config, but public inference constructs
  the model without LoRA and non-strictly loads state. Plan 016 closes that gap.
- Metric/generation failures can yield partial summaries and SingMOS may execute
  through a network-backed `torch.hub` path. Final gating must be complete and offline.

## Roadmap-wide hard boundaries

- Do not treat ordinary speech, diagnostic benchmark audio, or synthetic Music3
  as native score-aligned singing training data.
- Do not substitute speech for the score-matched native-singing primary
  condition in Plan 012; speech is secondary evidence only.
- Do not train on unknown, prohibited, revoked, or unverified rights/consent.
- Do not invent a full Mongolian G2P or convert study hypotheses into phonetic facts.
- Do not use MN-PHON-32/250 as the final singing test set.
- Do not alter pilot selection or final acceptance thresholds after seeing final results.
- Do not silently skip invalid data, fall back from requested CUDA to CPU, accept
  partial evaluation, or load mismatched checkpoints non-strictly.
- Do not commit raw audio, identities/consent documents, preprocessed shards,
  AudioVAE latents, checkpoints, optimizer states, or generated audio.
- Do not upload a model/dataset or create an external release without separate authorization.

## Findings considered and rejected or deferred

- **Copy the upstream 160k-step/four-H100 full-model schedule:** rejected as a
  default for a smaller Mongolian LoRA. Plans 017–018 measure and freeze a
  project-specific bounded horizon.
- **Train immediately on local speech/unknown-rights audio:** rejected. Plans
  013–014 require explicitly allowed native singing and score alignment.
- **Use synthetic music as native ground truth:** rejected. It remains optional
  exploratory evidence only.
- **Require Mandarin preservation with the Mongolian adapter enabled:** rejected
  as a model-selection veto. Adapter-disabled base routing and catastrophic
  enabled-adapter validity are hard gates; moderate Mandarin change is reported.
- **Build distributed/cloud preemption before the first 4070 smoke:** deferred
  to conditional Plan 015B. Basic staged/hash-verified checkpoint correctness
  remains in Plan 015A.
- **Choose hyperparameters or pass thresholds after final-test listening:**
  rejected. Plan 018 freezes both before Plan 019/020.
- **Automatically publish the final adapter:** deferred. Local acceptance does
  not grant external upload, distribution, or deployment permission.
- **Keep training after failed final acceptance:** rejected for this roadmap.
  Preserve the rejection and author Plan 021 with a new hypothesis.

## Audit scope note

This continuation surveyed training configuration/runner/runtime/checkpointing,
preprocessing/data loading, LoRA save/load paths, benchmark/evidence schemas,
evaluation metrics/completeness, manifests, tests, CI, and the Milestone 0
report. It did not load model weights, run CUDA, inspect private/raw audio,
validate corpus contracts, benchmark distributed performance, audit every neural
kernel, or perform a dependency-vulnerability scan. Those unknowns are expressed
as gates and STOP conditions rather than assumed away.
