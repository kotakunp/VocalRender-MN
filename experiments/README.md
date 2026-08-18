# Milestone 0 experiment contract

Numbered experiment directories are evidence containers, not launchers. Each
implemented experiment owns a concise `README.md`, deterministic checked-in
inputs under `config/`, and (once a run is actually performed) an immutable
machine record at `results/run.json`. Later runs append a new uniquely named
record such as `results/run-<run-id>.json`; an earlier record is never edited
to improve its result.

## Run-record schema

Records use the versioned `milestone-run/v1` shape:

```json
{
  "schema_version": "milestone-run/v1",
  "run_id": "stable-run-id",
  "status": "success|blocked|failed",
  "experiment": "numbered-experiment-name",
  "command": "sanitized reproduction command",
  "git_sha": "repository commit or unknown",
  "started_at": "UTC timestamp",
  "finished_at": "UTC timestamp",
  "environment": {"python": "version", "platform": "sanitized", "packages": {}},
  "inputs": [{"id": "semantic-input-id", "path": "repository-relative/path", "sha256": "..."}],
  "outputs": [{"path": "ignored-relative/path", "sha256": "...", "bytes": 0}],
  "warnings": [],
  "blocker": null,
  "notes": "interpretation limits and evidence links"
}
```

`status` is required. A `blocked` record must contain a nonempty `blocker` and
must not claim an output that was not produced. A `failed` record retains the
reproducible error class and command without secrets. Timestamps are UTC;
deterministic tests may supply a fixed timestamp or keep volatile run metadata
outside content-hashed result data.

## Sanitization and evidence policy

Before committing a README or run record, replace absolute home paths with
repository-relative paths or a short sanitized name. Never commit usernames,
speaker identities, secrets, service tokens, checkpoint payloads, caches, raw
audio, or generated model artifacts. Speaker references use approved
pseudonyms only. Input and output provenance is represented by semantic paths,
manifest/revision IDs, and SHA-256 checksums.

Experiment READMEs state the question, hypothesis, exact command, inputs,
interpretation limits, and whether pronunciation/native-quality conclusions
are explicitly out of scope. Config files must be deterministic and contain
no credentials. Results describe observed tool output; they do not copy
planned counts or turn fragmentation into a pronunciation claim.

## Current Milestone 0 records

| Experiment | Status | Interpretation |
| --- | --- | --- |
| `001_upstream_smoke_test` | blocked | CPU-only PyTorch/no CUDA; model loading and generation were not started |
| `002_tokenizer_audit` | success | tokenizer mechanics only |
| `003_phonetic_benchmark` | success | UniMorph orthographic candidates only |
| `004_frontend_baseline` | success | explicit score preservation; no inference or listening |
| `005_vocalrender_mn_lora` | blocked | prerequisites-only; training is not authorized |
| `006_native_reference_study` | frozen kit | 32 approved scores; 0 takes; 0 ratings; recordings are Plan 012 |

The directories for experiments 001–004 are owned by their respective
experiment executors. Experiment 005 intentionally has no executable config
or result record until its prerequisites are approved. Experiment 006 is the
Plan 010 study kit; it is not a listening result.
