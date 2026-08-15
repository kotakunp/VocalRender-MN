# Plan 007: Build a read-only Mongolian tokenizer audit

> **Executor instructions**: Inspect the tokenizer; never save, extend, or
> mutate it. Reports describe fragmentation and unknown-token behavior, not
> pronunciation correctness. Follow every verification gate and update this
> plan's row in `plans/README.md` when done.
>
> **Drift check (run first)**:
> `git diff --stat c0ab96e..HEAD -- pretrained_models/VocalRender-Pro resources benchmarks/MN-PHON-250 src/khalkha_frontend scripts/mn tests experiments/002_tokenizer_audit`
> Confirm Plans 003, 004, and 005 are `DONE`.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: `plans/003-create-frontend-foundation.md`,
  `plans/004-add-morphology-and-context-mining.md`,
  `plans/005-canonicalize-phonetic-benchmark.md`
- **Category**: performance / research tooling
- **Planned at**: commit `c0ab96e`, 2026-08-15

## Why this matters

Before changing tokens or training embeddings, the project must know how the
released VocalRender-Pro tokenizer represents Mongolian Cyrillic, benchmark
items, common words, and inflected forms. A reproducible audit identifies
unknown tokens and fragmentation hotspots while preserving the checkpoint.
The result guides the raw-text versus override/explicit-phone experiments; it
does not by itself justify modifying the tokenizer.

## Current state

- `pretrained_models/VocalRender-Pro/` contains `tokenizer.json` (~6.8 MB),
  `tokenizer_config.json`, model config, weights, and AudioVAE weights.
- `pretrained_models/VocalRender-Pro/config.json` reports architecture
  `voxcpm2` and LM vocab size 73,448.
- `tokenizer_config.json` names `LlamaTokenizer`, with `<unk>` as unknown token.
- `scripts/infer_vocalrender_svs_single.py:73-75` loads the tokenizer from the
  checkpoint and reconciles config vocab size in memory:

  ```python
  tokenizer = LlamaTokenizerFast.from_pretrained(str(ckpt_path))
  if len(tokenizer) != config.lm_config.vocab_size:
      config.lm_config.vocab_size = len(tokenizer)
  ```

- `scripts/setup_svs_tokenizer.py:23-31` mutates a tokenizer and saves it. That
  script is **not** an implementation pattern for the audit and must not be
  called.
- Audit inputs after prior plans:
  `benchmarks/MN-PHON-250/manifest.yaml`,
  `resources/lexicon/most_frequent_words.csv`, and
  `resources/unimorph_khk/`.
- Required character probes: `Ө ө Ү ү Ё ё Ь ь Ъ ъ`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused tests | `python -m pytest -q tests/test_tokenizer_audit.py` | all pass |
| CLI help | `python scripts/mn/audit_tokenizer.py --help` | exit 0 |
| Real audit | `python scripts/mn/audit_tokenizer.py --checkpoint pretrained_models/VocalRender-Pro --benchmark benchmarks/MN-PHON-250/manifest.yaml --resources-root resources --output-dir experiments/002_tokenizer_audit/results --offline` | exit 0; JSON and Markdown reports created |
| Full tests | `python -m pytest -q` | all pass |
| Format/lint | `python -m black --check src/khalkha_frontend scripts/mn tests` then `python -m flake8 src/khalkha_frontend scripts/mn tests` | both exit 0 |

## Scope

**In scope:**

- `src/khalkha_frontend/tokenizer_audit.py`
- `src/khalkha_frontend/__init__.py` for selected stable audit types/functions
- `scripts/mn/audit_tokenizer.py`
- `tests/test_tokenizer_audit.py`
- synthetic tokenizer/input fixtures under `tests/fixtures/tokenizer_audit/`
- `experiments/002_tokenizer_audit/README.md`
- `experiments/002_tokenizer_audit/config/audit.yaml`
- `experiments/002_tokenizer_audit/results/tokenizer_audit.json`
- `experiments/002_tokenizer_audit/results/tokenizer_audit.md`

**Out of scope:**

- Any write under `pretrained_models/`.
- `add_tokens`, `save_pretrained`, embedding resize, tokenizer setup, model
  loading, inference, or training.
- Declaring fragmented text unpronounceable or well-pronounced.
- Comparing acoustic output; Plan 009 handles experiments.
- Exhaustively processing every UniMorph row by default if a bounded,
  deterministic sample is sufficient.

## Git workflow

- Branch: `codex/007-tokenizer-audit`
- Suggested commits:
  `feat: add Mongolian tokenizer audit` and
  `docs: record VocalRender-Pro tokenizer baseline`.
- Do not push/open a PR unless instructed.

## Steps

### Step 1: Define tokenizer-agnostic audit records and metrics

In `tokenizer_audit.py`, define immutable records/protocols so unit tests use a
fake tokenizer. At minimum capture per sample:

- source and stable source item ID;
- original/normalized text;
- Unicode code points for special-character probes;
- token IDs and token strings (bounded in human report);
- character count, token count, tokens-per-character;
- optional syllable count and tokens-per-syllable only when an evidence-backed
  segmentation is available;
- unknown token count/presence;
- round-trip decoded text and mismatch flag;
- fragmentation flags based on transparent configurable thresholds.

Aggregate by source, character, target group, and word-length bucket. Report
median, p90/p95, max, unknown rate, round-trip mismatch rate, and histogram
buckets. Do not call a tokenization "bad" solely because it uses multiple
pieces; call it fragmented relative to the documented threshold.

**Verify**:
fake-tokenizer tests cover empty input, one/multiple tokens, `<unk>`, round-trip
mismatch, Unicode code points, and percentile calculations.

### Step 2: Build deterministic input collectors

Collectors must return stable IDs and deduplicate only identical source+text:

1. fixed special-character probes;
2. all 250 benchmark items;
3. high-frequency words, bounded/configurable and sorted by the source file;
4. UniMorph surface forms/lemmas, with a deterministic cap and stratification
   that includes inflected forms rather than only the first rows;
5. optional evidence-backed syllables when available, otherwise omit
   tokens-per-syllable.

Include input-source manifest IDs/revisions in the report. If a resource is
missing, emit a warning and continue with available sources unless it was
explicitly required by CLI flags.

**Verify**:
tests prove stable ordering/capping and confirm all 250 benchmark IDs are
included in a real-input dry run.

### Step 3: Load the local tokenizer offline and enforce read-only behavior

The CLI/library integration layer loads only tokenizer files via
`LlamaTokenizerFast.from_pretrained(checkpoint, local_files_only=True)` when
`--offline` is set. Before and after the audit:

- hash `tokenizer.json` and `tokenizer_config.json`;
- record tokenizer length, class, special tokens, and unknown token ID;
- assert hashes and directory file list are unchanged;
- never call mutating tokenizer methods.

Do not load `model.safetensors` or `audiovae.pth`. Isolate tokenizer imports so
fake-tokenizer unit tests do not require checkpoint files.

**Verify**:
real CLI reports unchanged hashes and no file under `pretrained_models/` appears
in `git status` or has a modified timestamp/hash attributable to the audit.

### Step 4: Implement JSON and Markdown reports

JSON is canonical and versioned. Include:

- schema/tool version and run timestamp;
- checkpoint path as repository-relative, tokenizer config/hash, vocab size;
- exact config/thresholds and input source metadata;
- aggregate metrics and per-probe/per-benchmark details;
- warning/error list;
- explicit limitations: tokenization is not pronunciation/native-quality
  evidence.

Markdown summarizes special letters, benchmark group distributions, most
fragmented items, unknowns, round-trip mismatches, and next experimental
questions. It must not dump all token sequences when a bounded table plus JSON
is enough.

Avoid absolute user paths and personal data in committed reports. If timestamp
prevents reproducible diffing, support `--generated-at` or separate volatile
run metadata from deterministic results.

**Verify**:

- JSON parses and its declared counts match detailed records;
- Markdown values are derived from JSON in the same run;
- rerunning with a fixed timestamp/config produces byte-identical reports.

### Step 5: Add CLI and experiment documentation

`scripts/mn/audit_tokenizer.py` supports:

- `--checkpoint`, `--benchmark`, `--resources-root`, `--config`, `--output-dir`;
- `--offline` defaulting true for local checkpoints;
- sample caps/fragmentation thresholds;
- `--generated-at` for deterministic testing;
- `--fail-on-unknown` and `--fail-on-roundtrip-mismatch` for CI-style use,
  while fragmentation remains informational by default.

`experiments/002_tokenizer_audit/README.md` records purpose, exact command,
hardware requirements (CPU only; no model weights loaded), interpretation, and
the decision gate: do not modify tokenizer until results are reviewed alongside
audio/benchmark evidence.

**Verify**:
CLI help, focused tests, and the real audit command all exit 0.

## Test plan

- Use a minimal fake tokenizer protocol for all metric/collector unit tests.
- Real checkpoint test is marked `integration` and skipped with a clear reason
  when tokenizer files are absent.
- Hash/read-only test must cover both success and an injected tokenizer error.
- Golden report fixture uses fixed time/config to verify deterministic JSON and
  Markdown.
- Assert reports contain no absolute `C:\Users\...` path.

## Done criteria

- [ ] Audit includes special letters, all 250 benchmark items, frequency words,
  and a documented deterministic UniMorph sample.
- [ ] JSON/Markdown reports agree and state limitations.
- [ ] Checkpoint tokenizer hashes and file list are unchanged.
- [ ] No model weights are loaded and no tokenizer is saved/extended.
- [ ] Fixed-input reruns are deterministic.
- [ ] `python -m pytest -q` passes; Black and flake8 pass.
- [ ] `plans/README.md` marks Plan 007 `DONE`.

## STOP conditions

Stop and report if:

- tokenizer files are missing/corrupt or require network access despite the
  observed local checkpoint;
- a tokenizer API mutates files/cache inside the checkpoint directory;
- the benchmark/resource schema differs from Plans 004/005;
- a stakeholder asks to extend tokens before baseline results are reviewed;
- the report would expose absolute personal paths or speech-speaker identifiers.

## Maintenance notes

- Re-run and version the report when checkpoint/tokenizer or input-resource
  revisions change.
- Fragmentation thresholds are monitoring parameters, not linguistic truths.
- Reviewer focus: read-only guarantees, deterministic sampling, and metric
  denominators.
