# Plan 013: Establish the training-corpus eligibility and leakage-safe split contract

> **Executor instructions**: This plan builds the gate; it does not approve a
> corpus. Work on `main`, preserve local data, and never infer rights from file
> presence. Subagents do not commit. The primary integrator reviews and commits
> with the user's configured Git identity and no co-author trailers.
>
> **Drift check (run first)**:
> `git diff --stat 1bf7bb8..HEAD -- data resources DATA_SOURCES.md src scripts tests .gitignore`

## Status

- **Status**: DONE
- **Priority**: P1
- **Effort**: L
- **Risk**: HIGH
- **Depends on**: Plan 009
- **Category**: data governance / evaluation integrity
- **Planned at**: commit `1bf7bb8`, 2026-08-15

## Why this matters

`data/raw/manifest.yaml:13-96` permits `unknown` provenance/use states, and the
known local speech/frequency resources remain unknown-rights. There is no
machine-enforced training eligibility or singer/song/session split. A valid SVS
run needs score-aligned native singing whose consent and training use are
explicitly allowed, with frozen splits that prevent memorized songs or voices
from inflating evaluation.

## Scope

**In scope:** versioned corpus manifest/schema/validator, pseudonymous identity
keys, rights gate, leakage-safe split generator, exclusion/quarantine report,
tracked small metadata under `data/manifests/mn_svs/`, documentation and tests.

**Out of scope:** acquiring audio, changing rights, score annotation,
preprocessing, training, committing raw media/PII, or admitting ordinary speech
as SVS training data.

## Contract

### 1. Define fail-closed eligibility

Each source and item must record stable pseudonymous IDs, relative audio/score
references, SHA-256, duration, language/variety, vocal type, singer/song/session
group keys, provenance locator, consent reference, license, redistribution,
research-evaluation use, training use, derivative-model permission, and review
status. Only explicit `allowed` plus approved review is eligible. `unknown`,
missing, expired, revoked, or conflicting fields are excluded with reason.

No real name, email, phone, contract content, or private storage URL belongs in
Git. Consent references are opaque IDs resolvable only in an operator-controlled
store.

### 2. Freeze leakage-safe splits

Always make test song-disjoint from train/validation. Declare whether singer
and session must also be disjoint based on corpus size; default to singer- and
song-disjoint test and song-disjoint validation. Grouped deterministic hashing
assigns whole groups, never individual clips. A split override requires a
checked-in reason before annotation outcomes are reviewed.

Prompt clips must come from the same song when required by VocalRender but be
non-overlapping in time with the target. A test target may not use train audio
as a prompt. Store prompt-target intervals and mechanically reject overlap.

Reserve the final test split once. MN-PHON-32 and synthetic Music3 are excluded
from training and final test; the former is diagnostic, the latter optional
exploratory evidence.

### 3. Add CLI gates and tracked metadata exceptions

Add `.gitignore` exceptions narrowly for `data/manifests/**` while continuing
to ignore audio, latents, Arrow shards, and checkpoints. Commands must validate
eligibility, generate a deterministic split manifest, verify group/interval
disjointness, and emit aggregate counts/durations plus excluded reasons without
speaker identities.

Example:

```powershell
python scripts/mn/validate_training_corpus.py data/manifests/mn_svs/corpus.yaml
python scripts/mn/split_training_corpus.py --manifest data/manifests/mn_svs/corpus.yaml --output data/manifests/mn_svs/splits.yaml
```

Both commands exit nonzero when zero eligible native-singing hours remain or a
leak is found. They must not rewrite an already frozen split unless an explicit
new version/output is chosen.

### 4. Document approvals and revocation

Update `DATA_SOURCES.md` with the corpus's source-level provenance and use
limits. Define operator sign-off, manifest versioning, revocation handling, and
derived-artifact deletion/retention policy. A revoked item invalidates dependent
preprocessed hashes and future runs; historical records remain but are marked
non-releasable.

## Test plan

- Fixtures cover allowed, unknown, prohibited, revoked, missing-checksum, PII,
  mixed-license, duplicate audio, and overlapping prompt/target intervals.
- Property tests confirm grouped splits are deterministic and disjoint.
- Validate path containment and reject traversal/symlink escape.
- Run full pytest, Black, flake8, YAML parsing, and a Git ignored/tracked check.

## Done criteria

- [ ] Unknown rights can never pass the training gate.
- [ ] Split and prompt policies are machine validated and frozen by checksum.
- [ ] Diagnostic/synthetic sources cannot enter train or final test.
- [ ] Only pseudonymous small manifests are trackable; media/PII remain ignored.
- [ ] External rights/consent approval is recorded before status becomes DONE.

## STOP conditions

Stop if training/derivative-model permission is ambiguous, consent cannot be
verified, group identifiers are insufficient to detect leakage, or the only
available material is speech rather than score-aligned singing. Report the
eligible count honestly; zero is a valid blocked result.

## Maintenance notes

Corpus and split versions are content-addressed inputs to every preprocessing,
pilot, and full run. Any eligible-item or grouping change creates a new version
and invalidates downstream caches.
