"""Repository scanner implementation."""

from __future__ import annotations

import os
from pathlib import Path

from config.scanner_config import ScannerConfig

from .file_filters import classify_file, should_skip_hidden_file
from .models import RepositoryManifest, ScannedFile


def _iter_candidate_files(root: Path, config: ScannerConfig):
    """Yield candidate file paths in deterministic order."""
    for current_root, dirs, files in os.walk(root, topdown=True):
        dirs[:] = sorted(d for d in dirs if not config.is_excluded_dir(d))
        for file_name in sorted(files):
            candidate = Path(current_root) / file_name
            rel = candidate.relative_to(root)

            if should_skip_hidden_file(candidate, config.include_hidden):
                continue
            if config.matches_exclude_glob(rel):
                continue
            if not config.allows_extension(candidate):
                continue
            try:
                size_bytes = candidate.stat().st_size
            except OSError:
                continue
            if size_bytes > config.max_file_size_bytes:
                continue
            yield candidate, rel, size_bytes


def scan_repository(root: str | Path, config: ScannerConfig | None = None) -> RepositoryManifest:
    """Scan a repository and return a normalized manifest."""
    scan_config = config or ScannerConfig()
    root_path = Path(root).resolve()

    files: list[ScannedFile] = []
    for candidate, rel, size_bytes in _iter_candidate_files(root_path, scan_config):
        files.append(
            ScannedFile(
                path=candidate,
                relative_path=rel,
                size_bytes=size_bytes,
                suffix=candidate.suffix.lower(),
                kind=classify_file(rel),
            )
        )

    files.sort(key=lambda item: item.relative_path.as_posix())
    return RepositoryManifest(root=root_path, files=tuple(files))
