# VocalRender-Pro Mongolian tokenizer audit

## Baseline

- Checkpoint: `pretrained_models/VocalRender-Pro`
- Tokenizer class: `LlamaTokenizer`
- Audited records: 1260
- Unknown rate: 0.0000
- Round-trip mismatch rate: 0.0000

## Required character probes

| Character | Code points | Tokens | Unknown |
|---|---|---:|---:|
| `Ө` | `U+04E8` | 3 | 0 |
| `ө` | `U+04E9` | 3 | 0 |
| `Ү` | `U+04AE` | 3 | 0 |
| `ү` | `U+04AF` | 3 | 0 |
| `Ё` | `U+0401` | 3 | 0 |
| `ё` | `U+0451` | 3 | 0 |
| `Ь` | `U+042C` | 3 | 0 |
| `ь` | `U+044C` | 2 | 0 |
| `Ъ` | `U+042A` | 3 | 0 |
| `ъ` | `U+044A` | 2 | 0 |

## Fragmentation summary

- Median tokens/character: 1.0
- P90: 1.375
- P95: 1.5714285714285714
- Max: 3.0
- Fragmented records: 68

| Source item | Text | Tokens/character | Unknown |
|---|---|---:|---:|
| `char-01` | `Ө` | 3.000 | 0 |
| `char-02` | `ө` | 3.000 | 0 |
| `char-03` | `Ү` | 3.000 | 0 |
| `char-04` | `ү` | 3.000 | 0 |
| `char-05` | `Ё` | 3.000 | 0 |
| `char-06` | `ё` | 3.000 | 0 |
| `char-07` | `Ь` | 3.000 | 0 |
| `char-09` | `Ъ` | 3.000 | 0 |
| `char-08` | `ь` | 2.000 | 0 |
| `char-10` | `ъ` | 2.000 | 0 |
| `benchmark:MNPHON_005` | `лө` | 2.000 | 0 |
| `benchmark:MNPHON_007` | `лү` | 2.000 | 0 |
| `benchmark:MNPHON_012` | `өл` | 2.000 | 0 |
| `benchmark:MNPHON_014` | `үл` | 2.000 | 0 |
| `benchmark:MNPHON_019` | `өлө` | 2.000 | 0 |
| `benchmark:MNPHON_021` | `үлү` | 2.000 | 0 |
| `benchmark:MNPHON_072` | `өг` | 2.000 | 0 |
| `benchmark:MNPHON_074` | `үг` | 2.000 | 0 |
| `benchmark:MNPHON_079` | `өгө` | 2.000 | 0 |
| `benchmark:MNPHON_081` | `үгү` | 2.000 | 0 |

## Benchmark target groups

| Group | Records | Unknown rate |
|---|---:|---:|
| `G` | 70 | 0.0000 |
| `H` | 60 | 0.0000 |
| `L` | 60 | 0.0000 |
| `PALATALIZATION` | 60 | 0.0000 |

## Word-length buckets

| Bucket | Records | Median tokens/character |
|---|---:|---:|
| `1-3` | 131 | 1.0 |
| `12+` | 32 | 1.0 |
| `4-7` | 588 | 1.0 |
| `8-11` | 509 | 0.9090909090909091 |

## Limitations

Token fragmentation and unknown-token behavior describe tokenizer mechanics only; they are not pronunciation or native-quality evidence.
Do not modify or extend the tokenizer until these results are reviewed with audio and benchmark evidence.
