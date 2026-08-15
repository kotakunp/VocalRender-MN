# fmt: off

"""Independent Khalkha text frontend primitives.

The package normalizes text conservatively and represents unresolved
pronunciation explicitly. It does not import VocalRender, PyTorch, or acquire
resources; callers inject :class:`ResourcePaths` when they need local data.
"""

from .normalize import normalize_text
from .resources import ResourcePaths, ResourceProblem, default_resource_paths
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
    "EvidenceRef",
    "FrontendResult",
    "NormalizedText",
    "PronunciationUnit",
    "ResolutionStatus",
    "ResourcePaths",
    "ResourceProblem",
    "default_resource_paths",
    "TextIssue",
    "TextIssueKind",
    "normalize_text",
]

# fmt: on
