"""Query parsing utilities for retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedQuery:
    raw: str
    tokens: tuple[str, ...]
    symbols: tuple[str, ...]


def parse_query(query: str) -> ParsedQuery:
    """Extract likely symbol tokens from a user query."""
    lowered = query.strip().lower()
    words = tuple(re.findall(r"[a-zA-Z_][a-zA-Z0-9_\.]*", lowered))

    stop = {
        "why",
        "is",
        "the",
        "a",
        "an",
        "to",
        "in",
        "of",
        "and",
        "or",
        "for",
        "variable",
        "function",
        "class",
    }
    symbols = tuple(w for w in words if w not in stop)
    return ParsedQuery(raw=query, tokens=words, symbols=symbols)