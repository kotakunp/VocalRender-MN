# Experiment 003: orthographic context mining

This experiment mines reproducible spelling candidates from the semantic
`resources/unimorph_khk/` input. The local frequency CSV is excluded from the
checked-in run because its source and redistribution rights are unknown. The
run recorded here used source git SHA
`1394fb413594550cba0c7ec6f65f423bc072f45d`; source identities and revisions
remain in the resource manifest. No input resource or canonical benchmark was
modified.

## Question and limits

Can the configured UniMorph input produce a deterministic,
bounded set of literal contexts for later manual benchmark review? Yes: the
run produced 2,858 candidates under `context-mining/v1`. These are
orthographic selectors only. They do not establish phonemes, IPA values,
allophones, or pronunciation quality, and no pronunciation field was filled.

Run from the repository root with the project Python environment:

```text
python scripts/mn/mine_contexts.py --config experiments/003_phonetic_benchmark/config/context_mining.yaml --output-json experiments/003_phonetic_benchmark/results/context_candidates.json
```

The recorded execution used the bundled CPython 3.12.13 runtime. The exact
sanitized commands, timestamps, input hashes, output checksum, and exit codes
are in `results/run.json`.

## Result summary

The benchmark validator returned `250 valid items; 0 audio takes; 0 ratings;
0 warnings` with exit code 0. Context mining returned exit code 0 and an empty
warning list. Candidate counts were:

| source | candidates |
| --- | ---: |
| unimorph_lemma | 1,404 |
| unimorph_surface | 1,454 |
| **total** | **2,858** |

The configured groups were `L`, `G`, `H`, `PALATALIZATION`, and `NG`, with a
per-pattern limit of 100 and UniMorph source-row limit of 5,000. The canonical
machine-readable output is
`results/context_candidates.json`; its candidates retain source, word,
occurrence, literal neighbors, and the explicit orthographic-selector note.

## Review boundary

These candidates may be selected for a human review set, but the mining CLI
never edits `benchmarks/MN-PHON-250/manifest.yaml`. Native-speaker validation,
linguistic literature, and traceable speech evidence are required before any
candidate can support a pronunciation override or resolved phonemic/phone
field. Raw speech and the unknown-rights frequency lexicon are not consumed by
this checked-in experiment.
