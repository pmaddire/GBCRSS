"""Filtering and classification helpers for repository scanning."""

from __future__ import annotations

from pathlib import Path

CONFIG_FILENAMES = {
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup.py",
    "setup.cfg",
    "tox.ini",
    ".env",
}

CONFIG_EXTENSIONS = {".toml", ".ini", ".cfg", ".yaml", ".yml", ".json"}


def classify_file(relative_path: Path) -> str:
    """Classify file type for downstream indexing priorities."""
    name = relative_path.name.lower()
    suffix = relative_path.suffix.lower()
    rel = relative_path.as_posix().lower()

    if "/tests/" in f"/{rel}" or name.startswith("test_") or name.endswith("_test.py"):
        return "test"
    if name in CONFIG_FILENAMES or suffix in CONFIG_EXTENSIONS:
        return "config"
    if suffix in {".py", ".pyi"}:
        return "source"
    return "other"


def should_skip_hidden_file(path: Path, include_hidden: bool) -> bool:
    """Exclude hidden files unless explicitly enabled."""
    return (not include_hidden) and path.name.startswith(".")
