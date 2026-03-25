"""Phase 2 parser fallback tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from parser.ast_parser import parse_python_source
from parser.models import ModuleParseResult
from parser.tree_sitter_adapter import parse_with_fallback


class _FakeTreeSitterSuccess:
    def parse_file(self, path: Path) -> ModuleParseResult:
        return ModuleParseResult(file=path)


class _FakeTreeSitterPartial:
    def parse_file(self, path: Path) -> ModuleParseResult:
        return ModuleParseResult(file=path, parse_errors=("incomplete",))


class _FakeTreeSitterFailure:
    def parse_file(self, path: Path) -> ModuleParseResult:
        raise RuntimeError("boom")


class ParserPhaseTests(unittest.TestCase):
    def test_ast_parser_extracts_core_symbols(self) -> None:
        source = (
            "import os\n"
            "from pkg import util\n"
            "X = 1\n\n"
            "def compute_diff(state, prediction):\n"
            "    \"\"\"doc\"\"\"\n"
            "    diff = state - prediction\n"
            "    return normalize(diff)\n\n"
            "class Runner(Base):\n"
            "    mode = 'fast'\n"
            "    def run(self):\n"
            "        return compute_diff(5, 3)\n"
        )
        result = parse_python_source(source, file="sample.py")

        self.assertEqual(len(result.functions), 1)
        self.assertEqual(result.functions[0].name, "compute_diff")
        self.assertIn("state", result.functions[0].variables_read)
        self.assertIn("diff", result.functions[0].variables_written)
        self.assertIn("normalize", result.functions[0].functions_called)

        self.assertEqual(len(result.classes), 1)
        self.assertEqual(result.classes[0].name, "Runner")
        self.assertIn("Base", result.classes[0].base_classes)
        self.assertIn("run", result.classes[0].methods)

        self.assertEqual(len(result.imports), 2)
        self.assertEqual(len(result.assignments), 1)

    def test_fallback_when_tree_sitter_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mod.py"
            path.write_text("def f(x):\n    return x\n", encoding="utf-8")

            result = parse_with_fallback(path, tree_sitter=None)

            self.assertEqual(result.backend, "ast")
            self.assertEqual(result.fallback_reason, "tree_sitter_unavailable")
            self.assertEqual(result.result.functions[0].name, "f")

    def test_fallback_when_tree_sitter_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mod.py"
            path.write_text("def f(x):\n    return x\n", encoding="utf-8")

            result = parse_with_fallback(path, tree_sitter=_FakeTreeSitterFailure())

            self.assertEqual(result.backend, "ast")
            self.assertTrue(result.fallback_reason.startswith("tree_sitter_failed:"))
            self.assertEqual(result.result.functions[0].name, "f")

    def test_fallback_when_tree_sitter_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mod.py"
            path.write_text("def f(x):\n    return x\n", encoding="utf-8")

            result = parse_with_fallback(path, tree_sitter=_FakeTreeSitterPartial())

            self.assertEqual(result.backend, "ast")
            self.assertEqual(result.fallback_reason, "tree_sitter_partial_or_error")
            self.assertEqual(result.result.functions[0].name, "f")

    def test_tree_sitter_success_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mod.py"
            path.write_text("def f(x):\n    return x\n", encoding="utf-8")

            result = parse_with_fallback(path, tree_sitter=_FakeTreeSitterSuccess())

            self.assertEqual(result.backend, "tree_sitter")
            self.assertIsNone(result.fallback_reason)


if __name__ == "__main__":
    unittest.main()