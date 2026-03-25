"""Context builder for minimal LLM prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .snippet_selector import RankedSnippet, estimate_tokens, select_snippets


@dataclass(frozen=True, slots=True)
class ContextPayload:
    query: str
    snippets: tuple[RankedSnippet, ...]
    total_tokens_estimate: int


def build_context(
    query: str,
    ranked_snippets: list[RankedSnippet],
    *,
    token_budget: int = 800,
    mandatory_node_ids: set[str] | None = None,
) -> ContextPayload:
    """Build minimal context payload for LLM usage."""
    selected = select_snippets(
        ranked_snippets,
        token_budget=token_budget,
        mandatory_node_ids=mandatory_node_ids,
    )
    total = sum(estimate_tokens(item.content) for item in selected)
    return ContextPayload(query=query, snippets=selected, total_tokens_estimate=total)