# VocalRender-MN Milestone 0 report

Date: 2026-08-15  
Status: foundation complete; model inference infrastructure blocked

## 1. Implemented foundation and verification

Plans 001–008 established the verification baseline, semantic resource layout,
provenance records, Khalkha frontend types, morphology/context tools,
MN-PHON-250, evidence-gated phonology scaffolds, tokenizer audit, and the
score-preserving VocalRender adapter. The implementation history from the
upstream baseline is recorded by commits `74c3018` through `1394fb4`.

Milestone 0 deterministic gates were rerun at source revision `1394fb4`:

- `python -m pytest -q`: 126 passed; two upstream PyTorch deprecation warnings;
- Black: 32 files unchanged;
- flake8 with the repository's 120-character/E203 policy: exit 0;
- benchmark validator: 250 valid items, 0 audio takes, 0 ratings, 0 warnings;
- tokenizer audit: exit 0, with the run in
  [`experiments/002_tokenizer_audit/results/run.json`](../experiments/002_tokenizer_audit/results/run.json);
- UniMorph-only context mining: exit 0, with 2,858 candidates in
  [`experiments/003_phonetic_benchmark/results/run.json`](../experiments/003_phonetic_benchmark/results/run.json);
- frontend conversion and upstream annotation-helper regression: exit 0, two
  lyric units, three notes, and melisma mapping `[0, 0, 1]`.

No test or experiment changed `src/vocalrender/`, a tokenizer, checkpoint
weights, AudioVAE, LocDiT, LocEnc, or the model architecture.

## 2. Data and resources found

The authoritative rights inventory is [`DATA_SOURCES.md`](../DATA_SOURCES.md),
with machine-readable records in [`resources/manifest.yaml`](../resources/manifest.yaml)
and [`data/raw/manifest.yaml`](../data/raw/manifest.yaml).

| Semantic resource | Local observation | Provenance/use status |
| --- | ---: | --- |
| `resources/unimorph_khk/khk` | 30,143 lines | CC BY-SA 3.0; research use allowed; training status unknown |
| `resources/unimorph_khk/khk.derivations` | 1,629 lines | same manifest entry and restrictions |
| `resources/unimorph_khk/khk.segmentations` | 30,129 lines | same manifest entry and restrictions |
| `resources/lexicon/most_frequent_words.csv` | 251 local-only lines | source, license, redistribution, research, and training rights unknown |
| `data/raw/speech/mbspeech` | 90 CSV files; 639,631 bytes | transcript/reference only; rights unknown |
| `data/raw/speech/spoken_words` | 49,636 files; 298,391,124 bytes | 42,397 Opus, 7,229 TextGrid, 5 CSV, 4 TXT, 1 log; consent and rights require verification |
| `data/raw/benchmark_tts` | 0 files | placeholder; rights unknown |
| `data/raw/native_speech` | 0 files | placeholder; acquisition/consent absent |
| `data/raw/native_singing` | 0 files | placeholder; no singing payload |
| `data/raw/music3` | 0 files | placeholder; provider terms/provenance absent |

Inventory counts were measured without opening payload content: recursively
enumerate files under each listed semantic root, group by extension, and sum
`Length`; count resource rows with `Get-Content <path> | Measure-Object -Line`.
Re-run those commands locally because ignored payload counts may change without
a Git commit. The manifests, rather than these volatile counts, remain the
authority for permitted use.

The unknown-rights frequency CSV was deliberately excluded from checked-in
tokenizer records and the final context-mining output. No local data is treated
as training-eligible merely because it exists.

## 3. Missing evidence and permissions

- No consented, licensed native Mongolian singing corpus with explicit score
  alignment is available.
- The local speech collections have unresolved license, redistribution,
  consent, and training-use status.
- The frequency lexicon has no identified source or permitted-use evidence.
- Native speech references, benchmark TTS, and Music3 take manifests are empty.
- The phonology workspace contains five `research_required` targets with null
  symbols, zero evidence records, and zero pronunciation overrides.
- No GPU/storage budget or leakage-safe singer/song split has been approved for
  adaptation work.

These gaps block LoRA design and any claim that a pronunciation or allophone
rule is established.

## 4. Upstream smoke outcome

Experiment 001 is `blocked`, not failed. The available environment has Python
3.12.13 and PyTorch `2.13.0+cpu`; CUDA availability is false, with no CUDA
runtime or GPU device. The unchanged inference script would fall back to CPU
before loading the local 9.5 GB-class checkpoint, so the bounded-run policy
stopped before model loading or generation. No audio was produced.

The exact command, checkpoint/tokenizer hashes, prompt-audio metadata, and
remediation are in
[`experiments/001_upstream_smoke_test/results/run.json`](../experiments/001_upstream_smoke_test/results/run.json).
Retry by appending a new run record in an approved CUDA-enabled environment;
do not modify upstream code to erase this environment distinction.

## 5. Tokenizer findings

The current VocalRender-Pro tokenizer reports length 73,850 and base vocabulary
size 73,440. Across 1,260 audited records, unknown-token and round-trip mismatch
rates are both 0.0. Median tokens per character is 1.0, P95 is
1.5714285714285714, maximum is 3.0, and 68 records exceed the configured 1.5
fragmentation threshold. All ten required Ө/Ү/Ё/Ь/Ъ case probes have zero
unknown tokens, although individual probes use two or three tokens.

These measurements describe token mechanics only. They neither demonstrate nor
refute correct Mongolian pronunciation, and they do not justify changing the
released tokenizer without controlled audio evidence.

## 6. MN-PHON-250 status

The canonical manifest validates 250 items: G 70, H 60, L 60, and
PALATALIZATION 60. All 250 remain `untested`; expected phoneme and phone fields
are null, evidence-reference count is zero, and the audio/rating manifests
contain zero takes and zero ratings. Experiment 003 provides 2,858 deterministic
UniMorph orthographic candidates for later manual selection, not phone labels.

No benchmark traffic-light or pronunciation-quality conclusion is possible
until traceable audio and independent native ratings exist.

## 7. Frontend capability boundary

The frontend can preserve conservative Unicode normalization issues, query
UniMorph, mine literal orthographic contexts, represent unresolved
syllable/phoneme/phone candidates, enforce evidence on resolved values, and
flatten explicit score units to VocalRender's `word`, `pitch`, `note`,
`pitch2word`, and `bpm` contract. It rejects missing alignment, invalid notes,
pitch/BPM errors, silent upstream defaults, and ambiguous unit-to-note mapping.

It does not infer score alignment from a sentence, supply a comprehensive
Mongolian G2P, resolve the five phonology targets, alter the tokenizer, or send
explicit phones into the released checkpoint. Phones and evidence remain in
the `mn_frontend` sidecar; current inference receives raw lyric units.

## 8. Evidence gate for linguistic rules

A syllabification, G2P, pronunciation override, or allophone rule may be added
only when its scope is explicit and its stable evidence IDs point to reviewed
linguistic literature, consented native speech/singing, or a documented native
speaker protocol. Recurring model output alone, generic multilingual behavior,
LLM memory, and one synthetic take are insufficient. Every promoted rule must
include regression tests and leave unresolved contexts unresolved.

## 9. Frozen native-reference study kit

Plan 010 supersedes the earlier position-only / one-note selection sketch.
The frozen kit lives in
[`experiments/006_native_reference_study`](../experiments/006_native_reference_study):
reviewed context annotations, approved lyric-to-note alignments, and 32
BPM-96 / C4 / `<NOTE_2>` scores under `config/scores/`. Selection used
group-specific context quotas; SHA-256 broke ties only among equal-diversity
sets. `хүүхэд` remains `хүү | хэд`.

The kit is frozen with 0 takes and 0 ratings. Plan 012 is the same-score
sung study and still requires a consented Standard Khalkha singer, three
raters, and a successful Plan 011 CUDA smoke. Do not start LoRA or bulk
generation from this kit.
