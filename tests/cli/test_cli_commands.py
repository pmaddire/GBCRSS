"""Phase 15 CLI integration tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from cli.app import app


class CliCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_index_command_outputs_manifest_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir(parents=True, exist_ok=True)
            (root / "src" / "a.py").write_text("print('x')\n", encoding="utf-8")

            result = self.runner.invoke(app, ["index", str(root)])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("total_files", result.output)

    def test_query_and_debug_commands(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "mod.py"
            target.write_text(
                "def compute_diff(a,b):\n"
                "    diff = a-b\n"
                "    return diff\n"
                "def run():\n"
                "    return compute_diff(2,1)\n",
                encoding="utf-8",
            )

            query = self.runner.invoke(app, ["query", str(target), "diff"])
            self.assertEqual(query.exit_code, 0)
            self.assertIn("compute_diff", query.output)

            debug = self.runner.invoke(app, ["debug", str(target), "why diff"])
            self.assertEqual(debug.exit_code, 0)
            self.assertIn("variable_modifications", debug.output)


if __name__ == "__main__":
    unittest.main()