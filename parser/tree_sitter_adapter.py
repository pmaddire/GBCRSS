"""Tree-sitter adapter contract and graceful fallback for parsing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .ast_parser import parse_python_file
from .models import ModuleParseResult


class TreeSitterParser(Protocol):
    """Protocol for a tree-sitter-backed parser implementation."""

    def parse_file(self, path: Path) -> ModuleParseResult:
        """Parse a file and return module parse result."""


@dataclass(slots=True)
class ParserFallbackResult:
    """Result with parser backend metadata."""

    result: ModuleParseResult
    backend: str
    fallback_reason: str | None = None


def parse_with_fallback(path: str | Path, tree_sitter: TreeSitterParser | None = None) -> ParserFallbackResult:
    """Use tree-sitter when available, otherwise fallback to stdlib AST parser."""
    file_path = Path(path)

    if tree_sitter is None:
        return ParserFallbackResult(
            result=parse_python_file(file_path),
            backend="ast",
            fallback_reason="tree_sitter_unavailable",
        )

    try:
        ts_result = tree_sitter.parse_file(file_path)
    except Exception as exc:  # pragma: no cover - defensive fallback
        return ParserFallbackResult(
            result=parse_python_file(file_path),
            backend="ast",
            fallback_reason=f"tree_sitter_failed:{exc.__class__.__name__}",
        )

    if ts_result.parse_errors:
        return ParserFallbackResult(
            result=parse_python_file(file_path),
            backend="ast",
            fallback_reason="tree_sitter_partial_or_error",
        )

    return ParserFallbackResult(result=ts_result, backend="tree_sitter")