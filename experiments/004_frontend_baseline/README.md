# Experiment 004: frontend baseline

This deterministic baseline checks that an explicit Mongolian score can cross
the neutral Khalkha frontend boundary into the released VocalRender score
shape. It does not claim a pronunciation, syllabification, or native-quality
result.

## Input and command

The checked-in input is [`config/score.json`](config/score.json), mirrored from
[`examples/mn_score_input.json`](../../examples/mn_score_input.json). The
verified command was:

```text
python scripts/mn/prepare_score.py examples/mn_score_input.json --output <temporary>/score.json --force
```

The command performs conservative normalization and explicit alignment
validation only. It does not load a checkpoint or run inference. The machine
result, hashes, and sanitized environment are in
[`results/run.json`](results/run.json).

## Observed score

The generated entry contains these exact score fields:

```text
word       = ["би", "хайр"]
pitch      = [60, 64, 67]
note       = ["<NOTE_8>", "<NOTE_8>", "<NOTE_4>"]
pitch2word = [0, 0, 1]
bpm        = 96
item_name  = "mn_demo"
```

The first unit, `би`, spans two notes (`<NOTE_8>`, `<NOTE_8>`); this is the
observed melisma and is retained in `pitch2word`. Both units have empty
normalization diagnostics. Both units have `pronunciation: null`, so the
unresolved pronunciation count is 2. No phones, syllable boundaries, or
allophone choices were inferred.

The prompt-audio reference remains namespaced in the frontend sidecar as
`data/raw/native_speech/demo_prompt.wav`; no audio was loaded, generated, or
listened to. Inference, listening, and native evaluation are all
`not_performed`.

## Tokenizer context

The tokenizer figures recorded in `results/run.json` are copied only from the
existing, hashed Plan 007 audit at
`experiments/002_tokenizer_audit/results/tokenizer_audit.json`: 1,260 audited
records, 0 unknown rate, 0 round-trip mismatch rate, median 1.0 tokens per
character, P90 1.375, P95 1.5714285714285714, maximum 3.0, and 68 fragmented
records. These are tokenizer-mechanics measurements, not Mongolian
pronunciation evidence.

The adapter also queried the live upstream `get_svs_token_maps` helper during
the run. It exposed 12 note tokens and 256 BPM tokens; `<NOTE_8>`, `<NOTE_4>`,
and BPM 96 were accepted. No model, checkpoint, or inference helper was
loaded.

## Interpretation limit

This experiment establishes score preservation and fail-closed token-boundary
validation only. It does not establish that raw Cyrillic lyrics are
pronunciation-correct, that the prompt audio is suitable, or that the released
model produces acceptable Mongolian singing. A native-speaker protocol and
evidence-linked phonology remain required before adding pronunciation rules.
