# Evidence-gated Khalkha phonology

This directory is intentionally incomplete. It supplies stable interfaces for
syllabification, phonemic representation, surface realization, and manual
pronunciation overrides without turning hypotheses into labels.

Promotion workflow:

1. Collect a candidate from benchmark or corpus mining.
2. Attach linguistic, native-speaker, or acoustic evidence with a stable ID.
3. Review whether the claim is phonemic or surface-level.
4. Add a narrowly scoped inventory, override, or allophone rule entry.
5. Add regression tests that reference the evidence ID.
6. Run benchmark comparison before widening scope.
7. Retain superseded evidence and rules with status metadata rather than
   rewriting history.

LLM memory, generic multilingual behavior, and one Music3 sample are not
sufficient evidence for a Mongolian phonology decision. Unknown words and
segments must remain explicit `research_required` results. The conceptual
segmentation examples in planning material are not production rules.

The phone inventory contains research targets for orthographic Л, Г, Х,
soft-sign/palatalization, and dorsal distinctions with null symbols. The
production pronunciation-override and allophone-rule resources begin empty.
