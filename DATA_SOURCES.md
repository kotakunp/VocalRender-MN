# Data and resource provenance

This project separates code licensing from data rights. The VocalRender code
is Apache-2.0, but that does not grant rights to datasets, speech recordings,
metadata, or generated outputs. Dataset licenses and consent terms control
their own artifacts. Generated audio may also be subject to the terms of the
service or model that produced it; those terms are not inferred from the
project's code license.

## Current inventory

| Manifest ID | Local path | Current intended use | Rights status |
| --- | --- | --- | --- |
| `unimorph_khk` | `resources/unimorph_khk` | Morphology/reference work; source: `https://github.com/unimorph/khk` | CC BY-SA 3.0 is stated in the local README; attribution/share-alike required; training status unknown |
| `mongolian_frequency_lexicon` | `resources/lexicon` | Lexicon/reference work; expected CSV is local-only and ignored | Source, license, redistribution, and training rights unknown |
| `phonology_workspace` | `resources/phonology` | Evidence-backed phonology artifacts when available | No artifacts or rights evidence established |
| `mbspeech_reference_transcripts` | `data/raw/speech/mbspeech` | Research/reference transcripts in Milestone 0 | License, redistribution, and training status unknown |
| `spoken_words_reference_audio` | `data/raw/speech/spoken_words` | Research/reference audio and metadata | License, consent scope, redistribution, and training status unknown |
| `benchmark_tts_collection` | `data/raw/benchmark_tts` | Future benchmark inputs | Unknown; placeholder only |
| `native_speech_collection` | `data/raw/native_speech` | Future research collection | Unknown; placeholder only |
| `native_singing_collection` | `data/raw/native_singing` | Future research collection | Unknown; placeholder only |
| `music3_generated_outputs` | `data/raw/music3` | Local generated-output records | Provider terms and provenance unknown |

The MN-SVS eligibility ledger is kept separately at
`data/manifests/mn_svs/corpus.yaml`. It may contain only pseudonymous item,
song, singer, and session group keys plus repository-relative media/score
references and SHA-256 checksums. The manifest does not approve a source by
itself: every item needs an opaque operator-resolvable consent reference,
explicitly allowed redistribution, research/evaluation, training, and
derivative-model permissions, and approved review status. Missing or unknown
evidence remains ineligible. The current ledger is empty because no approved
native Standard Khalkha score-aligned singing corpus has been supplied.

Ordinary speech under `data/raw/speech/` is research/reference material in
Milestone 0. It is not VocalRender training input. No resource is training-
eligible or redistributable merely because it is downloadable or present
locally; entries marked `unknown` require evidence before that use.

## Updating provenance

When acquiring, removing, or materially changing a resource, update the
corresponding entry in `resources/manifest.yaml` or `data/raw/manifest.yaml`
and this document. Record a source URL or local license evidence, revision or
acquisition date, and checksums where practical. Source identity and evidence,
not directory prefixes or assembly-history names, encode provenance.

Do not commit raw audio, checkpoints, generated Music3 audio, or personal
identifiers from speech metadata. Keep payloads local and commit only the
small manifests and documentation needed to make their status auditable.

## MN-SVS approval and revocation

An operator signs off a corpus version only after resolving each consent
reference in the private approval store and checking the source license and
use scope. The public manifest records only the opaque reference, review
status, version, checksums, and aggregate metadata. Any change to an eligible
item, checksum, group key, or rights field creates a new corpus version and
invalidates downstream preprocessing and split artifacts.

Revocation is fail-closed. A revoked or expired item remains in historical
records for audit but is marked non-releasable, excluded from future runs, and
invalidates dependent preprocessed hashes and derived artifacts. Operators
must delete local derived audio/latents/checkpoints when the approval terms
require deletion; otherwise retention is limited to non-releasable audit
metadata and documented legal/incident-retention obligations. No historical
split may be reused as a current training input after revocation.
