# Experiment 001: upstream VocalRender-Pro smoke

## Question and hypothesis

Can the unchanged upstream single-sample inference path load the already-local
VocalRender-Pro checkpoint and render the bundled Chinese control pair? A
successful 48 kHz nonempty WAV would establish an upstream environment
baseline independently of Mongolian frontend quality.

## Reproduction command

```text
python scripts/infer_vocalrender_svs_single.py --ckpt_dir pretrained_models/VocalRender-Pro --json_file examples/opencpop_demo.json --item_name 2003000087 --prompt_audio examples/prompt_audio/2003000081.wav --output outputs/plan009_upstream_smoke.wav
```

The bounded preflight on 2026-08-15 found a CPU-only PyTorch build and no CUDA
runtime or device. The script would silently replace the requested CUDA device
with CPU and then load approximately 9.5 GB of model weights. Because Plan 009
forbids an unbounded CPU inference detour, model loading and generation were not
started. `results/run.json` records this as an infrastructure-blocked run with
no output, not as a failed model or research hypothesis.

Retry only in an approved environment with a CUDA-enabled PyTorch build and a
compatible GPU budget. Do not change model code, download another checkpoint,
or treat this blocker as evidence about Mongolian pronunciation.

## Append-only runtime evidence

`results/run.json` is the original Plan 009 CPU-blocked record and is preserved.
The newer `results/run-20260815T150614Z-runtime-preflight.json` records the
fail-closed Plan 011 preflight against PyTorch `2.13.0+cpu`. A later start
record, `results/run-20260818T093537Z-runtime-preflight.json`, found this
shell on Python 3.14.7 with no PyTorch import and no CUDA host. Both stopped
before model construction. Neither is a model or Mongolian-quality result.

The checked-in `results/index.json` is the append-only pointer. A future
approved CUDA host must run the preflight first, then append a new record rather
than rewriting earlier records. CPU inference requires an explicit
`--allow-cpu` opt-in and is not valid for this smoke.
