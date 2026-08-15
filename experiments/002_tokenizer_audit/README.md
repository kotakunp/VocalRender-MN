# Mongolian tokenizer audit

This is a read-only baseline for `pretrained_models/VocalRender-Pro`. It
loads only the local tokenizer files on CPU; it does not load model or
AudioVAE weights, extend the vocabulary, or save the tokenizer.

```text
python scripts/mn/audit_tokenizer.py --checkpoint pretrained_models/VocalRender-Pro --benchmark benchmarks/MN-PHON-250/manifest.yaml --resources-root resources --config experiments/002_tokenizer_audit/config/audit.yaml --output-dir experiments/002_tokenizer_audit/results --offline
```

The JSON report is canonical; Markdown is derived from the same run. Use
`--generated-at` for byte-stable comparisons. Fragmentation and unknown-token
rates describe tokenizer mechanics, not pronunciation or native quality. Do
not modify the tokenizer until this baseline is reviewed together with audio
and benchmark evidence.

The checked-in config sets `frequency_limit: 0` because the local frequency
CSV has unknown source and redistribution rights. Its content hash is still
recorded when the file is present, but its words are excluded from the
committed report. A researcher may opt into a local-only frequency sample by
overriding the limit without committing the resulting detailed records.
