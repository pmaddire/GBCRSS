"""Phase 17 regression query tests."""

from __future__ import annotations

import unittest
from pathlib import Path

import networkx as nx

from debugging.bug_localizer import localize_bug
from graphs.call_graph import build_call_graph
from graphs.variable_graph import build_variable_graph
from parser.ast_parser import parse_python_source


class QueryRegressionTests(unittest.TestCase):
    def _graph(self) -> nx.DiGraph:
        source = (
            "def compute_diff(a,b):\n"
            "    diff = a-b\n"
            "    return diff\n\n"
            "def update_state(a,b):\n"
            "    return compute_diff(a,b)\n"
        )
        module = parse_python_source(source, file=Path("src/reg.py"))
        return nx.compose(build_call_graph((module,)), build_variable_graph((module,)))

    def test_diff_debug_query_regression(self) -> None:
        report = localize_bug(self._graph(), "Why is diff exploding?")
        joined = "\n".join(report.ranked_candidates)
        self.assertIn("compute_diff", joined)

    def test_caller_debug_query_regression(self) -> None:
        report = localize_bug(self._graph(), "Who calls compute_diff?")
        joined = "\n".join(report.ranked_candidates)
        self.assertIn("update_state", joined)


if __name__ == "__main__":
    unittest.main()