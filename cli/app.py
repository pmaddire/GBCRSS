"""Typer entrypoint for GCIE CLI."""

from __future__ import annotations

import json
import re

import typer

from .commands.adaptation import run_post_init_adaptation
from .commands.cache import cache_status, clear_cache, warm_cache
from .commands.context import run_context, run_context_basic
from .commands.context_slices import adaptive_profile_summary, clear_adaptive_profile, run_context_slices
from .commands.debug import run_debug
from .commands.index import run_index
from .commands.query import run_query
from .commands.setup import run_remove, run_setup

app = typer.Typer(help="GraphCode Intelligence Engine CLI")


def _query_tokens(query: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-zA-Z_./{}-][a-zA-Z0-9_./{}-]*", query.lower()))


def _auto_context_budget(query: str, intent: str | None) -> int | None:
    tokens = _query_tokens(query)
    lowered = query.lower()
    effective_intent = intent or "explore"

    file_terms = [token for token in tokens if "." in token or "/" in token or "{" in token]
    explicit_files = [token for token in file_terms if token.endswith((".py", ".jsx", ".js", ".tsx", ".ts", ".html"))]
    symbol_terms = [token for token in tokens if any(ch in token for ch in ("_", "/", ".", "{", "}"))]

    has_frontend = any(token.startswith(("frontend/", "frontend\\")) for token in file_terms)
    has_backend = any(
        token.endswith(".py") or token.startswith(("backend/", "server/", "api/"))
        for token in file_terms
    )
    cross_layer = has_frontend and has_backend

    stage_pipeline = any(term in lowered for term in ("stage", "pipeline", "planner", "plan", "build", "orchestr"))
    backend_config = any(term in lowered for term in ("backend", "config", "openai", "api_key", "llm", "no_ai", "backend_info"))
    ai_chain = any(term in lowered for term in ("openai", "llm", "model", "agent")) and has_backend
    same_layer_backend_pair = len([token for token in explicit_files if token.endswith(".py")]) >= 2 and not has_frontend
    has_api = "/api/" in lowered or any("/api/" in token for token in file_terms)

    if effective_intent in {"edit", "debug", "refactor"} and cross_layer and len(symbol_terms) >= 4:
        return 1200 if has_api else 1150
    if stage_pipeline and len(explicit_files) >= 2:
        return 1400
    if same_layer_backend_pair and (backend_config or ai_chain):
        return 1100
    if len(explicit_files) >= 3 and effective_intent in {"edit", "debug", "refactor"}:
        return 1200
    if effective_intent in {"edit", "debug"} and len(explicit_files) >= 2:
        return 1000
    if effective_intent == "refactor" and len(explicit_files) >= 2:
        return 1000
    return None


@app.command("index")
def index_cmd(path: str = typer.Argument(".")) -> None:
    result = run_index(path)
    typer.echo(json.dumps(result, indent=2))


@app.command("query")
def query_cmd(path: str, query: str, max_hops: int = 2) -> None:
    result = run_query(path, query, max_hops=max_hops)
    typer.echo(json.dumps(result, indent=2))


@app.command("debug")
def debug_cmd(path: str, query: str) -> None:
    result = run_debug(path, query)
    typer.echo(json.dumps(result, indent=2))


@app.command("context")
def context_cmd(
    path: str,
    query: str,
    budget: str = typer.Option("auto", "--budget"),
    intent: str | None = typer.Option(None, "--intent"),
    mode: str = typer.Option("basic", "--mode", help="context mode: basic or adaptive"),
) -> None:
    if budget == "auto":
        budget_val = _auto_context_budget(query, intent)
    else:
        budget_val = int(budget)

    if mode == "basic":
        result = run_context_basic(path, query, budget=budget_val, intent=intent)
    elif mode == "adaptive":
        result = run_context(path, query, budget=budget_val, intent=intent)
    else:
        raise typer.BadParameter("--mode must be 'basic' or 'adaptive'")
    typer.echo(json.dumps(result, indent=2))


@app.command("context-slices")
def context_slices_cmd(
    repo: str,
    query: str,
    profile: str | None = typer.Option("recall", "--profile"),
    stage_a_budget: int = typer.Option(400, "--stage-a"),
    stage_b_budget: int = typer.Option(800, "--stage-b"),
    max_total: int = typer.Option(1200, "--max-total"),
    intent: str | None = typer.Option(None, "--intent"),
    pin: str | None = typer.Option(None, "--pin"),
    pin_budget: int = typer.Option(300, "--pin-budget"),
    include_tests: bool = typer.Option(False, "--include-tests"),
) -> None:
    result = run_context_slices(
        repo,
        query,
        stage_a_budget=stage_a_budget,
        stage_b_budget=stage_b_budget,
        max_total=max_total,
        intent=intent,
        pin=pin,
        pin_budget=pin_budget,
        include_tests=include_tests,
        profile=profile,
    )
    typer.echo(json.dumps(result, indent=2))


@app.command("adaptive-profile")
def adaptive_profile_cmd(
    repo: str = typer.Argument("."),
    clear: bool = typer.Option(False, "--clear", help="Clear learned adaptive profile"),
) -> None:
    result = clear_adaptive_profile(repo) if clear else adaptive_profile_summary(repo)
    typer.echo(json.dumps(result, indent=2))


@app.command("adapt")
def adapt_cmd(
    repo: str = typer.Argument("."),
    benchmark_size: int = typer.Option(10, "--benchmark-size"),
    efficiency_iterations: int = typer.Option(5, "--efficiency-iterations"),
    clear_profile: bool = typer.Option(False, "--clear-profile"),
    adapt_workers: int = typer.Option(0, "--adapt-workers", help="Adaptation evaluation workers (0=auto)"),
) -> None:
    result = run_post_init_adaptation(
        repo,
        benchmark_size=benchmark_size,
        efficiency_iterations=efficiency_iterations,
        clear_profile=clear_profile,
        adapt_workers=(None if adapt_workers <= 0 else adapt_workers),
    )
    typer.echo(json.dumps(result, indent=2))


@app.command("setup")
def setup_cmd(
    path: str = typer.Argument("."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing setup files"),
    no_agent_usage: bool = typer.Option(False, "--no-agent-usage", help="Do not copy GCIE_USAGE.md"),
    no_setup_doc: bool = typer.Option(False, "--no-setup-doc", help="Do not copy SETUP_ANY_REPO.md"),
    no_index: bool = typer.Option(False, "--no-index", help="Skip initial indexing pass"),
    adapt: bool = typer.Option(False, "--adapt", help="Run post-init adaptation pipeline after setup"),
    adaptation_benchmark_size: int = typer.Option(10, "--adapt-benchmark-size"),
    adaptation_efficiency_iterations: int = typer.Option(5, "--adapt-efficiency-iterations"),
    adaptation_workers: int = typer.Option(0, "--adapt-workers", help="Adaptation evaluation workers (0=auto)"),
) -> None:
    result = run_setup(
        path,
        force=force,
        include_agent_usage=not no_agent_usage,
        include_setup_doc=not no_setup_doc,
        run_index_pass=not no_index,
        run_adaptation_pass=adapt,
        adaptation_benchmark_size=adaptation_benchmark_size,
        adaptation_efficiency_iterations=adaptation_efficiency_iterations,
        adaptation_workers=(None if adaptation_workers <= 0 else adaptation_workers),
    )
    typer.echo(json.dumps(result, indent=2))


@app.command("remove")
def remove_cmd(
    path: str = typer.Argument("."),
    remove_planning: bool = typer.Option(False, "--remove-planning", help="Also remove .planning artifacts"),
    keep_usage: bool = typer.Option(False, "--keep-usage", help="Keep GCIE_USAGE.md in place"),
    keep_setup_doc: bool = typer.Option(False, "--keep-setup-doc", help="Keep SETUP_ANY_REPO.md in place"),
) -> None:
    result = run_remove(
        path,
        remove_planning=remove_planning,
        remove_gcie_usage=not keep_usage,
        remove_setup_doc=not keep_setup_doc,
    )
    typer.echo(json.dumps(result, indent=2))

@app.command("cache-clear")
def cache_clear_cmd(path: str = typer.Argument(".")) -> None:
    result = clear_cache(path)
    typer.echo(json.dumps(result, indent=2))


@app.command("cache-status")
def cache_status_cmd(path: str = typer.Argument(".")) -> None:
    result = cache_status(path)
    typer.echo(json.dumps(result, indent=2))


@app.command("cache-warm")
def cache_warm_cmd(path: str = typer.Argument(".")) -> None:
    result = warm_cache(path)
    typer.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    app()



