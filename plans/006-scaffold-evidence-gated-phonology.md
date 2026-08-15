# Plan 006: Scaffold evidence-gated syllabification, G2P, and allophones

> **Executor instructions**: This is interface and evidence-management work,
> not permission to invent Mongolian phonology. An unresolved result is a
> successful result. Follow every gate and stop if a rule would rely on model
> memory or unsourced benchmark comments. Update this plan's row in
> `plans/README.md` when done.
>
> **Drift check (run first)**:
> `git diff --stat c0ab96e..HEAD -- src/khalkha_frontend resources/phonology benchmarks/MN-PHON-250 tests`
> Confirm Plans 003 and 005 are `DONE` and their public types/schema match the
> current-state assumptions below.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: `plans/003-create-frontend-foundation.md`,
  `plans/005-canonicalize-phonetic-benchmark.md`
- **Category**: architecture / research safety
- **Planned at**: commit `c0ab96e`, 2026-08-15

## Why this matters

VocalRender-MN needs stable seams for syllabification, phonemic representation,
context-sensitive realization, and manual pronunciation overrides before the
research has established the rules. Without explicit unresolved states and
evidence gates, placeholder code tends to harden guesses into training labels.
This plan makes experimentation possible while ensuring that unknown remains
machine-visible and reversible.

## Current state

- Plan 003 defines `ResolutionStatus`, evidence references, normalized text,
  and neutral frontend result types.
- Plan 005 makes `expected_phoneme` and `expected_phone` nullable and requires
  evidence for non-null values.
- `resources/phonology/` is the permanent home for small research metadata.
- The source prompt proposed the following modules:

  ```text
  src/khalkha_frontend/
  ├── syllabify.py
  ├── g2p.py
  ├── allophones.py
  └── phones.py
  ```

- The conceptual `чамдаа -> чам | даа` example is not sufficient evidence for
  a production rule or regression assertion.
- Orthographic Л, Г, Х, dorsal distinctions, soft signs, and secondary
  articulation are research targets, not fixed mappings.
- Three end-state input strategies remain open: raw Cyrillic only, lyrics plus
  phones, or raw text with explicit overrides. The scaffold must support all
  three without selecting one permanently.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused tests | `python -m pytest -q tests/test_syllabify.py tests/test_g2p.py tests/test_allophones.py tests/test_phone_registry.py` | all pass |
| Full tests | `python -m pytest -q` | all pass |
| Format | `python -m black --check src/khalkha_frontend tests` | exit 0 |
| Lint | `python -m flake8 src/khalkha_frontend tests` | exit 0 |
| Guess scan | `rg -n "[лгх]\s*=|expected_(phoneme|phone):\s*[^n]" src/khalkha_frontend resources/phonology tests` | no unsourced mapping matches |

## Scope

**In scope:**

- `src/khalkha_frontend/syllabify.py`
- `src/khalkha_frontend/g2p.py`
- `src/khalkha_frontend/allophones.py`
- `src/khalkha_frontend/phones.py`
- `src/khalkha_frontend/types.py` only for additive shared types/invariants
- `src/khalkha_frontend/__init__.py` for stable exports
- `resources/phonology/README.md`
- `resources/phonology/evidence.yaml`
- `resources/phonology/phone_inventory.yaml`
- `resources/phonology/pronunciation_overrides.yaml`
- `tests/test_syllabify.py`
- `tests/test_g2p.py`
- `tests/test_allophones.py`
- `tests/test_phone_registry.py`
- small synthetic YAML fixtures under `tests/fixtures/phonology/`

**Out of scope:**

- Filling a complete Cyrillic-to-IPA/phone mapping.
- Treating the draft benchmark's IPA-like comments as established evidence.
- Forced alignment, acoustic analysis, phone recognition, or native-speaker
  annotation collection.
- Changing VocalRender tokens, embeddings, model architecture, or training.
- Adding a language-specific third-party phonology library without separate
  evaluation.

## Git workflow

- Branch: `codex/006-evidence-gated-phonology`
- Suggested commit: `feat: scaffold evidence-gated Khalkha phonology`.
- Do not push/open a PR unless instructed.

## Steps

### Step 1: Define a shared resolution protocol

Extend `types.py` only as needed to represent:

- `SyllableCandidate(text, start, end, status, evidence, alternatives, notes)`;
- `PhonemeCandidate(symbols, status, evidence, source_text, notes)`;
- `PhoneCandidate(symbols, status, evidence, phonological_environment, notes)`;
- `PronunciationOverride` with stable ID, exact normalized orthography or item
  scope, supplied symbols, level (`phonemic` or `surface`), evidence/provenance,
  and optional expiration/review status.

Central invariants:

- `RESOLVED` and `OVERRIDDEN` values require nonempty evidence/provenance;
- alternatives remain ordered and individually evidence-tagged;
- an unresolved candidate keeps original text and a reason;
- source spans must cover the exact normalized substring;
- no API encodes unknown as an empty string that is indistinguishable from
  silence.

**Verify**:
focused type tests reject resolved/overridden candidates without evidence and
accept explicit unresolved candidates.

### Step 2: Create a conservative syllabifier interface

In `syllabify.py`, define a `Syllabifier` protocol and a default
`ConservativeSyllabifier`. Its Milestone 0 behavior:

1. accepts normalized lyric tokens/words;
2. applies only entries from an evidence-backed override/lexicon source;
3. if no supported segmentation exists, returns one
   `RESEARCH_REQUIRED` candidate spanning the entire word;
4. never silently splits before/after vowels;
5. preserves punctuation/special-token boundaries and issues from normalization;
6. can return multiple evidence-tagged alternatives without selecting one.

Provide explicit extension points for future rule sets and morphological hints.
Morphology may contribute a boundary *candidate*, not automatically establish a
singing syllable boundary.

Tests may use synthetic override words (`abc -> a|bc`) to prove mechanics. Do
not use those as Mongolian facts. For real Mongolian words, assert only
unresolved preservation unless the repo contains sourced evidence.

**Verify**:
`python -m pytest -q tests/test_syllabify.py` -> covers empty input, unresolved
whole-word fallback, synthetic override, alternatives, spans, and no vowel
heuristic.

### Step 3: Create a phone inventory that can be incomplete

In `phones.py`, define:

- `PhoneDefinition` with stable ID, optional symbol, level, articulatory tags,
  status, evidence refs, notes;
- `PhoneRegistry` loader for `phone_inventory.yaml`;
- uniqueness checks for IDs/symbols;
- lookup by ID/symbol;
- validation that a non-null established symbol has evidence;
- an explicit placeholder/research-target representation whose symbol is null.

Seed `phone_inventory.yaml` only with research targets for orthographic Л, Г,
Х, soft-sign/palatalization, and dorsal distinctions. Keep their actual
phonemic/surface symbols null and status `research_required` unless an explicit
source has been added and reviewed. Do not repeat candidate IPA from the draft
manifest as fact.

`evidence.yaml` should use stable IDs and fields for citation/source URL or
local path, evidence kind, reviewer/status, date, and notes. It may initially be
empty except schema metadata.

**Verify**:
`python -m pytest -q tests/test_phone_registry.py` -> real inventory loads,
research targets remain null, and invalid resolved fixtures fail.

### Step 4: Implement G2P as an evidence-gated resolver

In `g2p.py`, define a `G2PResolver` protocol and default resolver. Resolution
order:

1. exact caller-supplied manual override;
2. reviewed entry from `pronunciation_overrides.yaml` matching scope;
3. evidence-backed lexicon/registry entry;
4. unresolved `RESEARCH_REQUIRED` result preserving orthography.

The output must distinguish phonemic symbols from surface phones and must not
reuse a surface-phone override as a phonemic value. Expose diagnostics showing
which layer handled each unit. Do not build letter-by-letter fallback mappings.

`pronunciation_overrides.yaml` begins empty with schema/version documentation.
If example records are needed, put synthetic examples in test fixtures, not the
production resource.

**Verify**:
`python -m pytest -q tests/test_g2p.py` -> precedence, evidence requirements,
level separation, and unresolved fallback all pass.

### Step 5: Implement allophone resolution as a no-op until rules are sourced

In `allophones.py`, define:

- a typed phonological environment (neighboring phoneme IDs, word/morpheme
  boundary, position, optional score context);
- `AllophoneRule` with priority, input/output phone IDs, conditions, evidence,
  and status;
- deterministic rule ordering and conflict detection;
- `AllophoneResolver` that applies reviewed rules only.

With no reviewed rules, the resolver must return the phonemic candidate as
unresolved surface realization or retain an already explicit surface override.
It must not infer from letters Л/Г/Х directly.

Use synthetic fixture rules to test application, priority, conflict, and
evidence gating. Keep the production rule list empty for Milestone 0.

**Verify**:
`python -m pytest -q tests/test_allophones.py` -> empty production rules do not
fabricate phones; synthetic rules behave deterministically.

### Step 6: Document the evidence promotion workflow

In `resources/phonology/README.md`, document:

1. collect a candidate from benchmark/corpus mining;
2. attach linguistic/native/acoustic evidence with a stable evidence ID;
3. review the phonemic vs surface interpretation;
4. add a narrowly scoped inventory/override/rule entry;
5. add regression tests referencing the evidence ID;
6. run benchmark comparison before widening scope;
7. retain superseded evidence/rules with status rather than rewriting history.

Explicitly state that LLM memory, generic multilingual behavior, and one Music3
sample are not sufficient evidence.

**Verify**:
`rg -n "__GET__|__MAKE__|mn_ling" resources/phonology src/khalkha_frontend tests`
-> no matches.

## Test plan

- Production resource tests prove incompleteness is valid.
- Synthetic fixtures prove machinery without encoding Mongolian guesses.
- Real benchmark integration tests may assert that all 250 unresolved expected
  fields load, never that a given spelling has a particular phone.
- Test conflict handling, duplicate IDs, stale evidence refs, wrong phonemic vs
  surface levels, and exact-override precedence.

## Done criteria

- [ ] Unknown words/segments return explicit `RESEARCH_REQUIRED` values rather
  than exceptions, empty strings, or guessed phones.
- [ ] No resolved phone/phoneme/syllabification exists without evidence.
- [ ] Default production allophone rules and pronunciation overrides are empty
  unless the repo contains reviewed evidence.
- [ ] Synthetic tests demonstrate extension mechanics without masquerading as
  Mongolian linguistic facts.
- [ ] `python -m pytest -q` passes; Black and flake8 pass.
- [ ] No `src/vocalrender/**` file or model/tokenizer asset changed.
- [ ] `plans/README.md` marks Plan 006 `DONE`.

## STOP conditions

Stop and report if:

- an executor is asked to populate symbols from memory, an unsourced comment,
  or a generic web table without linguistic review;
- current benchmark evidence conventions cannot distinguish hypothesis from
  validated fact;
- a real rule is required to make tests pass;
- package types from Plan 003/005 drifted enough to require breaking public
  changes;
- implementing overrides would require modifying the upstream tokenizer/model.

## Maintenance notes

- Review evidence links and scope, not just code correctness.
- Narrow rules are preferable to broad mappings; expansion requires benchmark
  evidence across contexts.
- Keep phonemic and surface layers separate so future acoustic findings do not
  rewrite lexical representations.
