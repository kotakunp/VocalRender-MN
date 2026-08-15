"""Injected resolution of semantic local resource paths.

ResourcePaths locates data but never downloads or creates it. It recognizes
only permanent semantic directories and works independently of the process
current working directory.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True)
class ResourceProblem:
    """Structured diagnostic for a missing required resource directory."""

    path: Path
    message: str


@dataclass(frozen=True)
class ResourcePaths:
    """Repository-root-relative semantic paths selected by the caller."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "root",
            Path(self.root).expanduser().resolve(),
        )

    @classmethod
    def from_repository_root(cls, path: Path) -> "ResourcePaths":
        """Construct paths from an explicit repository root."""

        return cls(Path(path))

    @property
    def unimorph_khk(self) -> Path:
        return self.root / "resources" / "unimorph_khk"

    @property
    def lexicon(self) -> Path:
        return self.root / "resources" / "lexicon"

    @property
    def phonology(self) -> Path:
        return self.root / "resources" / "phonology"

    @property
    def speech(self) -> Path:
        return self.root / "data" / "raw" / "speech"

    @property
    def benchmark_tts(self) -> Path:
        return self.root / "data" / "raw" / "benchmark_tts"

    @property
    def native_speech(self) -> Path:
        return self.root / "data" / "raw" / "native_speech"

    @property
    def native_singing(self) -> Path:
        return self.root / "data" / "raw" / "native_singing"

    @property
    def music3(self) -> Path:
        return self.root / "data" / "raw" / "music3"

    def validate(self, require_raw_data: bool = False) -> Tuple[ResourceProblem, ...]:
        """Return missing-path diagnostics without exiting or creating paths.

        No directories are created by validation.
        """

        required = [self.unimorph_khk, self.lexicon, self.phonology]
        if require_raw_data:
            required.append(self.speech)
        return tuple(
            ResourceProblem(
                path,
                "required semantic resource directory is missing",
            )
            for path in required
            if not path.is_dir()
        )


def default_resource_paths() -> ResourcePaths:
    """Derive a source-checkout root without consulting the current directory.

    Callers can supply an explicit root for installed packages.
    """

    return ResourcePaths.from_repository_root(
        Path(__file__).resolve().parents[2],
    )
