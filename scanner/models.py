"""Data models for repository scanning."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FileKind = Literal["source", "test", "config", "other"]


@dataclass(frozen=True, slots=True)
class ScannedFile:
    """A file discovered by the repository scanner."""

    path: Path
    relative_path: Path
    size_bytes: int
    suffix: str
    kind: FileKind


@dataclass(frozen=True, slots=True)
class RepositoryManifest:
    """Normalized scanner output for downstream indexing."""

    root: Path
    files: tuple[ScannedFile, ...]

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def source_files(self) -> tuple[ScannedFile, ...]:
        return tuple(f for f in self.files if f.kind == "source")

    @property
    def test_files(self) -> tuple[ScannedFile, ...]:
        return tuple(f for f in self.files if f.kind == "test")

    @property
    def config_files(self) -> tuple[ScannedFile, ...]:
        return tuple(f for f in self.files if f.kind == "config")
