"""Route context requests between architecture-driven and normal modes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from llm_context.snippet_selector import estimate_tokens

from .architecture_bootstrap import ensure_initialized
from .architecture_slicer import slice_with_architecture, trim_snippets_to_budget
from .fallback_evaluator import should_fallback


NormalRunner = Callable[[], dict]


def _total_tokens(snippets: list[dict]) -> int:
    return sum(estimate_tokens(item.get("content", "")) for item in snippets)


def _record_fallback(repo_path: Path, reason: str | None, config: dict) -> None:
    if reason is None:
        return
    config_path = repo_path / ".gcie" / "context_config.json"
    config["fallback_reason"] = reason
    try:
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    except Exception:
        return


def route_context(
    repo: str,
    query: str,
    *,
    intent: str | None,
    max_total: int,
    profile: str | None,
    normal_runner: NormalRunner,
) -> dict:
    repo_path = Path(repo)
    config = ensure_initialized(repo_path)

    if not config.get("architecture_slicer_enabled", True):
        _record_fallback(repo_path, "architecture_disabled", config)
        payload = normal_runner()
        payload["fallback_reason"] = "architecture_disabled"
        return payload

    arch_result = slice_with_architecture(repo_path, query)
    fallback, reason = should_fallback(arch_result, config)
    if fallback:
        _record_fallback(repo_path, reason, config)
        payload = normal_runner()
        payload["fallback_reason"] = reason
        return payload

    trimmed = trim_snippets_to_budget(arch_result.snippets, max_total)
    return {
        "query": arch_result.query,
        "profile": profile,
        "mode": "architecture",
        "intent": intent,
        "confidence": arch_result.confidence,
        "matched_subsystems": arch_result.matched_subsystems,
        "snippets": trimmed,
        "token_estimate": _total_tokens(trimmed),
    }
