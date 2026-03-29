"""Snippet selection logic for LLM context packaging."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RankedSnippet:
    node_id: str
    content: str
    score: float


def estimate_tokens(text: str) -> int:
    """Cheap token estimate for budget management."""
    return max(1, len(text.split()))


def select_snippets(
    ranked: list[RankedSnippet],
    *,
    token_budget: int,
    mandatory_node_ids: set[str] | None = None,
) -> tuple[RankedSnippet, ...]:
    """Select minimal high-value snippets under token budget."""
    mandatory_node_ids = mandatory_node_ids or set()

    selected: list[RankedSnippet] = []
    seen_contents: set[str] = set()
    used_tokens = 0

    # First, include mandatory snippets if possible.
    for item in ranked:
        if item.node_id not in mandatory_node_ids:
            continue
        if item.content in seen_contents:
            continue
        t = estimate_tokens(item.content)
        if used_tokens + t > token_budget:
            continue
        selected.append(item)
        seen_contents.add(item.content)
        used_tokens += t

    # Then fill with highest score snippets.
    for item in sorted(ranked, key=lambda s: s.score, reverse=True):
        if item.content in seen_contents:
            continue
        t = estimate_tokens(item.content)
        if used_tokens + t > token_budget:
            continue
        selected.append(item)
        seen_contents.add(item.content)
        used_tokens += t

    return tuple(selected)
