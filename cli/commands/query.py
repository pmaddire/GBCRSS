"""CLI command: query."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from graphs.call_graph import build_call_graph
from graphs.variable_graph import build_variable_graph
from parser.ast_parser import parse_python_file
from retrieval.symbolic_retriever import symbolic_retrieve


def run_query(path: str, query: str, max_hops: int = 2) -> list[str]:
    target = Path(path)
    module = parse_python_file(target)
    graph = nx.compose(build_call_graph((module,)), build_variable_graph((module,)))
    candidates = symbolic_retrieve(graph, query, max_hops=max_hops)
    return [c.node_id for c in candidates]