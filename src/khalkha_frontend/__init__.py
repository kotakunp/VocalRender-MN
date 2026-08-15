"""Independent, evidence-aware Khalkha frontend and research utilities.

The package stays independent of VocalRender and preserves unresolved
pronunciation explicitly. Morphology and context labels remain orthographic
evidence; callers inject resource paths when local data is required.
"""

from .morphology import (
    DerivationRow,
    MorphAnalysis,
    MorphologyFormatError,
    MorphologyLookup,
    Segmentation,
    UniMorphKhalkha,
    analyze_word,
    segment_morphemes,
)
from .context_mining import (
    FrequencyRecord,
    OrthographicCandidate,
    candidate_to_dict,
    mine_frequency,
    mine_unimorph,
    mine_word,
    read_frequency_list,
)
from .normalize import normalize_text
from .resources import ResourcePaths, ResourceProblem, default_resource_paths
from .tokenizer_audit import (
    AuditSample,
    TokenizationRecord,
    TokenizerSnapshot,
    aggregate_records,
    aggregate_by_benchmark_group,
    aggregate_by_character,
    aggregate_by_word_length,
    collect_benchmark,
    collect_frequency,
    collect_special_probes,
    collect_unimorph,
    percentile,
    sha256_file,
    tokenize_sample,
    word_length_bucket,
)
from .types import (
    EvidenceRef,
    FrontendResult,
    NormalizedText,
    PronunciationUnit,
    ResolutionStatus,
    TextIssue,
    TextIssueKind,
)

__all__ = [
    "AuditSample",
    "DerivationRow",
    "EvidenceRef",
    "FrequencyRecord",
    "FrontendResult",
    "MorphAnalysis",
    "MorphologyFormatError",
    "MorphologyLookup",
    "NormalizedText",
    "OrthographicCandidate",
    "PronunciationUnit",
    "ResolutionStatus",
    "ResourcePaths",
    "ResourceProblem",
    "Segmentation",
    "TextIssue",
    "TextIssueKind",
    "TokenizationRecord",
    "TokenizerSnapshot",
    "UniMorphKhalkha",
    "aggregate_by_benchmark_group",
    "aggregate_by_character",
    "aggregate_by_word_length",
    "aggregate_records",
    "analyze_word",
    "candidate_to_dict",
    "collect_benchmark",
    "collect_frequency",
    "collect_special_probes",
    "collect_unimorph",
    "default_resource_paths",
    "mine_frequency",
    "mine_unimorph",
    "mine_word",
    "normalize_text",
    "percentile",
    "read_frequency_list",
    "segment_morphemes",
    "sha256_file",
    "tokenize_sample",
    "word_length_bucket",
]
