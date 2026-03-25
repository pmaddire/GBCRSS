"""CLI command: index."""

from __future__ import annotations

from pathlib import Path

from scanner.repository_scanner import scan_repository


def run_index(path: str) -> dict[str, int]:
    manifest = scan_repository(Path(path))
    return {
        "total_files": manifest.total_files,
        "source_files": len(manifest.source_files),
        "test_files": len(manifest.test_files),
        "config_files": len(manifest.config_files),
    }