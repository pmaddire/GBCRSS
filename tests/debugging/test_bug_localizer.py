"""Phase 13 bug localizer tests."""

from __future__ import annotations

import unittest
from pathlib import Path

import networkx as nx

from debugging.bug_localizer import localize_bug
from graphs.call_graph import build_call_graph
from graphs.variable_graph import build_variable_graph
from parser.ast_parser import parse_python_source


def _debug_graph() -> nx.DiGraph:
    source = (
        "def normalize(x):\n"
        "    return x\n\n"
        "def compute_diff(state, pred):\n"
        "    diff = state - pred\n"
        "    return normalize(diff)\n\n"
        "def update_state(s, p):\n"
        "    return compute_diff(s, p)\n\n"
        "def run_simulation():\n"
        "    return update_state(9, 2)\n"
    )
    m = parse_python_source(source, file=Path("src/sim.py"))
    return nx.compose(build_call_graph((m,)), build_variable_graph((m,)))


class BugLocalizerTests(unittest.TestCase):
    def test_localizes_diff_modification_flow(self) -> None:
        graph = _debug_graph()

        report = localize_bug(
            graph,
            "Why is variable diff exploding?",
            git_recency_by_node={"function:src/sim.py::compute_diff": 1.0},
            coverage_risk_by_node={"function:src/sim.py::compute_diff": 1.0},
        )

        self.assertIn("diff", report.target_symbols)
        self.assertTrue(any("compute_diff" in fn for fn in report.relevant_functions))
        self.assertTrue(any("compute_diff" in fn for fn in report.variable_modifications))
        self.assertGreaterEqual(len(report.call_chain), 1)

    def test_ranking_contains_expected_execution_nodes(self) -> None:
        graph = _debug_graph()

        report = localize_bug(graph, "trace run_simulation path")
        joined = "\n".join(report.ranked_candidates)

        self.assertIn("run_simulation", joined)
        self.assertIn("update_state", joined)


if __name__ == "__main__":
    unittest.main()