"""Typer entrypoint for GCIE CLI."""

from __future__ import annotations

import json

import typer

from .commands.cache import cache_status, clear_cache, warm_cache
from .commands.context import run_context
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