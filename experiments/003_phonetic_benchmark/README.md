# Orthographic context mining

This experiment mines reproducible spelling candidates from the semantic
`resources/lexicon/most_frequent_words.csv` and `resources/unimorph_khk/`
inputs. Their source identities and revisions are recorded in the resource
manifests; this experiment does not acquire or modify those inputs.

Run from the repository root:

```text
python scripts/mn/mine_contexts.py --config experiments/003_phonetic_benchmark/config/context_mining.yaml --output-json experiments/003_phonetic_benchmark/results/context_candidates.json
```

JSON is the canonical output schema (`context-mining/v1`). Each candidate
retains source, word, occurrence, spelling context, and an explicit note that
the label is an orthographic selector. A human may copy reviewed candidates
into `benchmarks/MN-PHON-250/` following its manifest and manual-review
workflow; the CLI never edits the canonical benchmark.

Orthographic patterns do not establish phonemes, IPA values, or allophones.
Native/linguistic validation and, where appropriate, raw-speech evidence are
required before any pronunciation field can be resolved. Raw speech is not
consumed by this text-only experiment.
