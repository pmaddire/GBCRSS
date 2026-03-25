"""Context builder for minimal LLM prompts."""

from __future__ import annotations

from dataclasses import dataclass

from .snippet_selector import RankedSnippet, estimate_tokens, select_snippets


@dataclass(frozen=True, slots=True)
class ContextPayload:
    query: str
    snippets: tuple[RankedSnippet, ...]
    total_tokens_estimate: int


_INTENT_BASE = {
    "edit": 300,
    "refactor": 600,
    "debug": 500,
    "explore": 400,
}


def _detect_intent(query: str) -> str:
    text = query.lower()
    if any(word in text for word in ("refactor", "rewrite", "migrate", "restructure")):
        return "refactor"
    if any(word in text for word in ("debug", "why", "error", "fail", "bug", "trace")):
        return "debug"
    if any(word in text for word in ("add", "change", "update", "extend", "modify", "remove", "rename")):
        return "edit"
    return "explore"


def _auto_budget(query: str, ranked_snippets: list[RankedSnippet], intent: str) -> int:
    """Compute a context budget that scales with intent, query, and candidate size."""
    q_tokens = estimate_tokens(query)
    count = len(ranked_snippets)

    base = _INTENT_BASE.get(intent, 400)
    budget = base + min(300, q_tokens * 10) + min(400, count * 30)
    return max(200, min(1600, budget))


def build_context(
    query: str,
    ranked_snippets: list[RankedSnippet],
    *,
    token_budget: int | None = 800,
    mandatory_node_ids: set[str] | None = None,
    intent: str | None = None,
) -> ContextPayload:
    """Build minimal context payload for LLM usage."""
    if token_budget is None:
        detected_intent = _detect_intent(query) if intent is None else intent
        token_budget = _auto_budget(query, ranked_snippets, detected_intent)

    selected = select_snippets(
        ranked_snippets,
        token_budget=token_budget,
        mandatory_node_ids=mandatory_node_ids,
    )
    total = sum(estimate_tokens(item.content) for item in selected)
    return ContextPayload(query=query, snippets=selected, total_tokens_estimate=total)