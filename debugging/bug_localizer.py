"""Bug localization workflow for GCIE debugging queries."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from retrieval.hybrid_retriever import hybrid_retrieve
from retrieval.query_parser import parse_query

from .execution_path_analyzer import neighborhood_path


@dataclass(frozen=True, slots=True)
class LocalizedBugReport:
    query: str
    target_symbols: tuple[str, ...]
    relevant_functions: tuple[str, ...]
    call_chain: tuple[str, ...]
    variable_modifications: tuple[str, ...]
    ranked_candidates: tuple[str, ...]


def _function_nodes_touching_symbol(graph: nx.DiGraph, symbol: str) -> tuple[str, ...]:
    out: set[str] = set()
    needle = symbol.lower()

    for src, dst, attrs in graph.edges(data=True):
        edge_type = str(attrs.get("type", ""))
        if edge_type not in {"WRITES", "MODIFIES", "READS"}:
            continue

        if str(dst).lower() == f"variable:{needle}" and str(src).startswith("function:"):
            out.add(str(src))

    return tuple(sorted(out))


def localize_bug(
    graph: nx.DiGraph,
    query: str,
    *,
    git_recency_by_node: dict[str, float] | None = None,
    coverage_risk_by_node: dict[str, float] | None = None,
) -> LocalizedBugReport:
    """Localize likely bug sources from a debugging query."""
    parsed = parse_query(query)
    symbols = parsed.symbols

    variable_mods: set[str] = set()
    for symbol in symbols:
        variable_mods.update(_function_nodes_touching_symbol(graph, symbol))

    hybrid = hybrid_retrieve(
        graph,
        query,
        git_recency_by_node=git_recency_by_node,
        coverage_risk_by_node=coverage_risk_by_node,
        max_hops=3,
        top_k=10,
    )
    ranked = tuple(c.node_id for c in hybrid)

    relevant_functions = tuple(
        node_id for node_id in ranked if node_id.startswith("function:")
    )

    chain: tuple[str, ...] = ()
    if relevant_functions:
        seed = relevant_functions[0]
        chain = neighborhood_path(graph, seed=seed, hops=2).nodes

    return LocalizedBugReport(
        query=query,
        target_symbols=symbols,
        relevant_functions=relevant_functions,
        call_chain=chain,
        variable_modifications=tuple(sorted(variable_mods)),
        ranked_candidates=ranked,
    )