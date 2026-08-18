# Native-reference study kit

This directory contains only deterministic study tooling and review queues. It
does not contain audio, identities, rater decisions, or inferred phonology.

The primary comparison is score-matched Standard Khalkha singing: the same
NFC raw-Cyrillic text, manually reviewed lyric units, C4 notes, and BPM are
used for the native singer and VocalRender-Pro conditions. Native speech is
secondary evidence and cannot replace a missing sung reference.

Context labels and lyric alignments are approved by `developer_01` and the
32-item kit is frozen. `хүүхэд` is retained as an exact regression fixture:
`хүү | хэд`, spans `[0,3]`/`[3,6]`, one MIDI-60 `<NOTE_2>` per unit.
Consented native-singer recordings remain Plan 012 and are not claimed here.

After freeze, recordings are randomized and blinded in a private operator
manifest. Raters receive only blind label, criterion, order, protocol, and
rating. Corrections append a new study/config version; prior cycles are never
rewritten.

The 0/1/2 articulation rubric and recurring-error rule are defined in Plan 012.
Music3 is optional context and is never native ground truth.
