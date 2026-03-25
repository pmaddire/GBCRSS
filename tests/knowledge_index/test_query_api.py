"""Phase 9 knowledge index query tests."""

from __future__ import annotations

import unittest
from pathlib import Path

from knowledge_index.index_builder import build_knowledge_index
from knowledge_index.query_api import (
    find_classes_inheriting_from,
    find_files_importing_module,
    find_functions_calling_function,
    find_functions_modifying_variable,
)
from parser.ast_parser import parse_python_source


class KnowledgeIndexQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        source = (
            "from pkg.base import Base\n"
            "from math import sqrt\n\n"
            "class Runner(Base):\n"
            "    def run(self):\n"
            "        return compute_diff(10, 5)\n\n"
            "def compute_diff(a, b):\n"
            "    diff = a - b\n"
            "    return diff\n\n"
            "def orchestrate():\n"
            "    return compute_diff(4, 2)\n"
        )
        module = parse_python_source(source, file=Path("src/engine.py"))
        self.store = build_knowledge_index((module,))

    def test_find_functions_modifying_variable(self) -> None:
        result = find_functions_modifying_variable(self.store, "diff")
        names = {fn.name for fn in result}
        self.assertEqual(names, {"compute_diff"})

    def test_find_functions_calling_function(self) -> None:
        result = find_functions_calling_function(self.store, "compute_diff")
        names = {fn.name for fn in result}
        self.assertEqual(names, {"orchestrate"})

    def test_find_files_importing_module(self) -> None:
        result = find_files_importing_module(self.store, "math")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].path, "src/engine.py")

    def test_find_classes_inheriting_from(self) -> None:
        result = find_classes_inheriting_from(self.store, "Base")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Runner")


if __name__ == "__main__":
    unittest.main()