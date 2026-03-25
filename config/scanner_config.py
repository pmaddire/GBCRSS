"""Scanner configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class ScannerConfig:
    """Configuration for repository scanning."""

    include_extensions: set[str] = field(
        default_factory=lambda: {
            ".py",
            ".pyi",
            ".md",
            ".txt",
            ".toml",
            ".yaml",
            ".yml",
            ".json",
            ".ini",
            ".cfg",
            ".rst",
            ".sh",
        }
    )
    exclude_dirs: set[str] = field(
        default_factory=lambda: {
            ".git",
            ".hg",
            ".svn",
            ".venv",
            "venv",
            "__pycache__",
            "node_modules",
            "build",
            "dist",
            ".pytest_cache",
            ".mypy_cache",
            ".idea",
            ".vscode",
        }
    )
    exclude_globs: tuple[str, ...] = ()
    max_file_size_bytes: int = 1_000_000
    include_hidden: bool = False

    def is_excluded_dir(self, directory_name: str) -> bool:
        """Return True if a directory should be skipped during scanning."""
        if not self.include_hidden and directory_name.startswith("."):
            return True
        return directory_name in self.exclude_dirs

    def allows_extension(self, path: Path) -> bool:
        """Return True when the file extension is in the allow-list."""
        return path.suffix.lower() in self.include_extensions

    def matches_exclude_glob(self, relative_path: Path) -> bool:
        """Return True when the path matches any configured exclusion glob."""
        return any(relative_path.match(pattern) for pattern in self.exclude_globs)

    @classmethod
    def from_extensions(
        cls,
        include_extensions: Iterable[str],
        *,
        max_file_size_bytes: int = 1_000_000,
        include_hidden: bool = False,
    ) -> "ScannerConfig":
        """Build config from extension iterable."""
        normalized = {
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in include_extensions
        }
        return cls(
            include_extensions=normalized,
            max_file_size_bytes=max_file_size_bytes,
            include_hidden=include_hidden,
        )
