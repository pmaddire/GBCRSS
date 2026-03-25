"""CLI command: debug."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from debugging.bug_localizer import localize_bug
from graphs.call_graph import build_call_graph
from graphs.variable_graph import build_variable_graph
from parser.ast_parser import parse_python_file


def run_debug(path: str, query: str) -> dict[str, list[str]]:
    target = Path(path)
    module = parse_python_file(target)
    graph = nx.compose(build_call_graph((module,)), build_variable_graph((module,)))
    report = localize_bug(graph, query)
    return {
        "relevant_functions": list(report.relevant_functions),
        "call_chain": list(report.call_chain),
        "variable_modifications": list(report.variable_modifications),
    }