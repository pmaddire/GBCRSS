"""CLI command: cache."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .context import _collect_repo_modules


def clear_cache(path: str) -> dict[str, str]:
    repo = Path(path)
    cache_dir = repo / ".gcie" / "cache"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
        return {"status": "cleared", "path": str(cache_dir)}
    return {"status": "missing", "path": str(cache_dir)}


def cache_status(path: str) -> dict[str, str]:
    repo = Path(path)
    cache_file = repo / ".gcie" / "cache" / "context_cache.json"
    if cache_file.exists():
        return {"status": "ready", "path": str(cache_file)}
    return {"status": "missing", "path": str(cache_file)}


def warm_cache(path: str) -> dict[str, str]:
    repo = Path(path)
    _collect_repo_modules(repo)
    cache_file = repo / ".gcie" / "cache" / "context_cache.json"
    if cache_file.exists():
        return {"status": "warmed", "path": str(cache_file)}
    return {"status": "missing", "path": str(cache_file)}