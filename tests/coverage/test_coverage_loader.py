"""Phase 8 coverage loader tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from coverage_integration.coverage_loader import load_coverage_json


class CoverageLoaderTests(unittest.TestCase):
    def test_missing_report_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "missing.json"
            report = load_coverage_json(path)
            self.assertEqual(report.files, ())

    def test_loads_partial_and_branch_metadata(self) -> None:
        payload = {
            "files": {
                "src/app.py": {
                    "executed_lines": [1, 2, 3],
                    "missing_lines": [4],
                    "summary": {
                        "percent_covered": 75.0,
                        "num_statements": 4,
                        "num_branches": 2,
                        "num_partial_branches": 1,
                    },
                }
            }
        }

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "coverage.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            report = load_coverage_json(path)
            self.assertEqual(len(report.files), 1)
            file_rec = report.files[0]
            self.assertEqual(file_rec.path, "src/app.py")
            self.assertEqual(file_rec.executed_lines, (1, 2, 3))
            self.assertEqual(file_rec.missing_lines, (4,))
            self.assertEqual(file_rec.num_branches, 2)
            self.assertEqual(file_rec.num_partial_branches, 1)


if __name__ == "__main__":
    unittest.main()