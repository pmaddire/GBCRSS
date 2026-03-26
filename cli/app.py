"""Typer entrypoint for GCIE CLI."""

from __future__ import annotations

import json
import re

import typer

from .commands.cache import cache_status, clear_cache, warm_cache
from .commands.context import run_context
from .commands.context_slices import run_context_slices
from .commands.debug import run_debug
from .commands.index import run_index
from .commands.query import run_query

app = typer.Typer(help="GraphCode Intelligence Engine CLI")


def _query_tokens(query: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-zA-Z_./{}-][a-zA-Z0-9_./{}-]*", query.lower()))


def _auto_context_budget(query: str, intent: str | None) -> int | None:
    tokens = _query_tokens(query)
    file_terms = [token for token in tokens if "." in token or "/" in token or "{" in token]
    symbol_terms = [token for token in tokens if any(ch in token for ch in ("_", "/", ".", "{", "}"))]
    explicit_files = [token for token in file_terms if token.endswith((".py", ".jsx", ".js", ".tsx", ".ts", ".html"))]
    cross_layer = any(token.startswith(("frontend/", "frontend\\")) for token in file_terms) and any(
        token.endswith(".py") or token.startswith(("backend/", "server/", "api/")) for token in file_terms
    )
    has_api = any("/api/" in token for token in file_terms) or "/api/" in query.lower()
    effective_intent = intent or "explore"

    if effective_intent in {"edit", "debug", "refactor"} and cross_layer and len(symbol_terms) >= 4:
        return 1200
    if effective_intent in {"edit", "debug"} and (len(explicit_files) >= 2 and len(symbol_terms) >= 4):
        return 1200 if has_api else 1000
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
) -> None:
    if budget == "auto":
        budget_val = _auto_context_budget(query, intent)
    else:
        budget_val = int(budget)

    result = run_context(path, query, budget=budget_val, intent=intent)
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
