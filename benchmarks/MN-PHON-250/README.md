# MN-PHON-250

MN-PHON-250 is a 250-item research benchmark for Standard Khalkha Mongolian
pronunciation targets in Cyrillic orthography. It is a comparison and annotation
instrument, not a claim that every item has a settled phonemic or surface-phone
analysis. The canonical item manifest keeps `expected_phoneme` and
`expected_phone` null until a traceable evidence record is reviewed.

## Audio roles

- `data/raw/native_speech/MN-PHON-250/` is the primary pronunciation reference.
- `data/raw/native_singing/phonetic/` is later singing ground truth and should
  be collected with appropriate consent and speaker pseudonyms.
- `data/raw/benchmark_tts/MN-PHON-250/` holds comparison TTS generations.
- `data/raw/music3/MN-PHON-250/` holds Music3 research runs, with run IDs such
  as `a`, `b`, and `c` when files actually exist.

Audio-take records use repository-relative forward-slash paths under one of
these semantic roots. Personal names, contact details, and raw credentials do
not belong in manifests; use a pseudonym and provenance reference instead.

## Manual ratings

Rate a declared take with an integer score:

- `2`: target pronunciation is acceptable for the reviewed criterion.
- `1`: partially acceptable, ambiguous, or requires review.
- `0`: unacceptable or clearly mismatched.

Ratings must reference both an existing item and an existing audio take, and
the rating item must match the take's item. A traffic-light view is derived
only when enough distinct rater pseudonyms exist; it is not stored as primary
truth. Unrated or insufficiently independent material remains `UNTESTED` or
`NEEDS_REVIEW`.

## Evidence workflow

1. Add a stable evidence reference to `evidence.yaml` or a repository-local
   source record. Expected phonemes/phones accept only linguistic literature,
   native speech/singing, or native-speaker validation evidence kinds.
2. Review whether the evidence supports a phonemic value, a surface phone, or
   only a research hypothesis.
3. Add the evidence reference before resolving an expected field.
4. Add an audio take and rating without exposing personal data.
5. Keep superseded interpretations as notes/status changes rather than
   rewriting item IDs or history.

Ordinary speech is reference material, not direct SVS training data in
Milestone 0. Music3 is a pronunciation research/teacher candidate, not the
final score-controlled inference engine.

## Validation

From the repository root:

```text
python scripts/mn/validate_benchmark.py benchmarks/MN-PHON-250/manifest.yaml
python scripts/mn/validate_benchmark.py benchmarks/MN-PHON-250/manifest.yaml --json-report report.json
python scripts/mn/validate_benchmark.py benchmarks/MN-PHON-250/manifest.yaml --strict-files
```

The default command permits absent audio payloads and reports them as warnings.
`--strict-files` turns missing referenced payloads into errors. Do not create
fake take or rating records merely to make a manifest non-empty.
