"""Phase 4 call graph tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from graphs.call_graph import build_call_graph
from parser.ast_parser import parse_python_source


class CallGraphTests(unittest.TestCase):
    def test_direct_and_nested_local_calls(self) -> None:
        source = (
            "def c():\n"
            "    return 1\n\n"
            "def b():\n"
            "    return c()\n\n"
            "def a():\n"
            "    return b()\n"
        )
        module = parse_python_source(source, file=Path("pkg/mod.py"))
        graph = build_call_graph((module,))

        self.assertIn(("function:pkg/mod.py::a", "function:pkg/mod.py::b"), graph.edges)
        self.assertIn(("function:pkg/mod.py::b", "function:pkg/mod.py::c"), graph.edges)

    def test_unresolved_calls_are_preserved(self) -> None:
        source = (
            "class Runner:\n"
            "    def run(self):\n"
            "        return self.helper()\n\n"
            "def entry():\n"
            "    x = Runner()\n"
            "    return x.run()\n"
        )
        module = parse_python_source(source, file=Path("pkg/runner.py"))
        graph = build_call_graph((module,))

        external_nodes = [n for n, attrs in graph.nodes(data=True) if attrs.get("type") == "external_function"]
        self.assertTrue(any(node.startswith("external:Runner") for node in external_nodes))
        self.assertTrue(any(node.startswith("external:x.run") for node in external_nodes))

    def test_import_alias_call_resolves_to_external_qualified_name(self) -> None:
        source = (
            "from math import sqrt\n\n"
            "def a():\n"
            "    return sqrt(4)\n"
        )
        module = parse_python_source(source, file=Path("pkg/calc.py"))
        graph = build_call_graph((module,))

        self.assertIn(("function:pkg/calc.py::a", "external:math.sqrt"), graph.edges)
        edge_data = graph.get_edge_data("function:pkg/calc.py::a", "external:math.sqrt")
        self.assertEqual(edge_data["type"], "CALLS")
        self.assertFalse(edge_data["resolved"])


if __name__ == "__main__":
    unittest.main()