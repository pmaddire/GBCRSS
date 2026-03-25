"""Typer entrypoint for GCIE CLI."""

from __future__ import annotations

import json

import typer

from .commands.cache import cache_status, clear_cache, warm_cache
from .commands.context import run_context
from .commands.context_slices import run_context_slices
from .commands.debug import run_debug
from .commands.index import run_index
from .commands.query import run_query

app = typer.Typer(help="GraphCode Intelligence Engine CLI")


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
        budget_val = None
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
