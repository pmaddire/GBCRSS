"""Phase 3 code structure graph tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from graphs.code_graph import build_code_structure_graph
from graphs.validators import validate_graph_integrity
from parser.ast_parser import parse_python_source


class CodeGraphTests(unittest.TestCase):
    def test_builds_expected_structure_edges(self) -> None:
        source = (
            "import os\n"
            "from pkg import tool\n\n"
            "class Runner:\n"
            "    def run(self):\n"
            "        return helper()\n\n"
            "def helper():\n"
            "    return 1\n"
        )
        module = parse_python_source(source, file=Path("src/app.py"))
        graph = build_code_structure_graph((module,))

        file_id = "file:src/app.py"
        class_id = "class:src/app.py::Runner"
        function_id = "function:src/app.py::helper"

        self.assertIn(file_id, graph.nodes)
        self.assertIn(class_id, graph.nodes)
        self.assertIn(function_id, graph.nodes)

        self.assertEqual(graph.nodes[file_id]["type"], "file")
        self.assertEqual(graph.nodes[class_id]["type"], "class")
        self.assertEqual(graph.nodes[function_id]["type"], "function")

        self.assertIn((file_id, class_id), graph.edges)
        self.assertIn((file_id, function_id), graph.edges)

        import_edges = [
            (u, v) for (u, v, d) in graph.edges(data=True) if d.get("type") == "IMPORTS"
        ]
        self.assertGreaterEqual(len(import_edges), 2)

    def test_graph_validators_detect_invalid_node(self) -> None:
        source = "def f():\n    return 1\n"
        module = parse_python_source(source, file=Path("demo.py"))
        graph = build_code_structure_graph((module,))

        graph.add_node("broken-node")

        errors = validate_graph_integrity(graph)
        self.assertTrue(any("missing attrs" in error for error in errors))

    def test_graph_validators_pass_for_valid_graph(self) -> None:
        source = "def f():\n    return 1\n"
        module = parse_python_source(source, file=Path("demo.py"))
        graph = build_code_structure_graph((module,))

        errors = validate_graph_integrity(graph)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()