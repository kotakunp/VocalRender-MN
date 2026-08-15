# fmt: off

from vocalrender.training.svs_raw_data import (
    convert_annotation_to_syllables,
    expand_syllables,
)


def test_one_mongolian_lyric_unit_maps_to_one_note():
    syllables = convert_annotation_to_syllables(
        ["сайн"],
        [60],
        ["<NOTE_4>"],
        [0],
    )

    assert syllables == [{"char": "сайн", "pitch": 60, "note": "<NOTE_4>"}]


def test_multi_character_lyric_unit_is_not_split():
    syllables = convert_annotation_to_syllables(
        ["хайр"],
        [62],
        ["<NOTE_8>"],
        [0],
    )

    assert syllables == [{"char": "хайр", "pitch": 62, "note": "<NOTE_8>"}]


def test_melisma_expands_with_shared_word_index():
    syllables = convert_annotation_to_syllables(
        ["хайр"],
        [62, 64],
        ["<NOTE_8>", "<NOTE_8>"],
        [0, 0],
    )

    assert expand_syllables(syllables) == [
        {"char": "хайр", "pitch": 62, "note": "<NOTE_8>", "word_idx": 0},
        {"char": "хайр", "pitch": 64, "note": "<NOTE_8>", "word_idx": 0},
    ]


def test_identical_adjacent_lyrics_keep_distinct_word_indices():
    syllables = convert_annotation_to_syllables(
        ["аа", "аа"],
        [60, 62],
        ["<NOTE_4>", "<NOTE_4>"],
        [0, 1],
    )

    assert expand_syllables(syllables) == [
        {"char": "аа", "pitch": 60, "note": "<NOTE_4>", "word_idx": 0},
        {"char": "аа", "pitch": 62, "note": "<NOTE_4>", "word_idx": 1},
    ]


def test_unmapped_lyric_unit_is_skipped_by_current_behavior():
    syllables = convert_annotation_to_syllables(
        ["сайн", "орхигдсон"],
        [60],
        ["<NOTE_4>"],
        [0],
    )

    assert syllables == [{"char": "сайн", "pitch": 60, "note": "<NOTE_4>"}]

# fmt: on
