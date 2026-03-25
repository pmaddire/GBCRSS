"""Phase 1 repository scanner tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config.scanner_config import ScannerConfig
from scanner.repository_scanner import scan_repository


class RepositoryScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write(self, relative_path: str, content: str = "x") -> None:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def test_manifest_ordering_is_deterministic(self) -> None:
        self._write("b/module.py", "print('b')")
        self._write("a/module.py", "print('a')")
        self._write("c/readme.md", "docs")

        manifest_one = scan_repository(self.root)
        manifest_two = scan_repository(self.root)

        paths_one = [item.relative_path.as_posix() for item in manifest_one.files]
        paths_two = [item.relative_path.as_posix() for item in manifest_two.files]

        self.assertEqual(paths_one, paths_two)
        self.assertEqual(paths_one, sorted(paths_one))

    def test_hidden_dirs_are_excluded_by_default(self) -> None:
        self._write(".hidden/secret.py", "print('secret')")
        self._write("visible/main.py", "print('ok')")

        manifest = scan_repository(self.root)
        paths = {item.relative_path.as_posix() for item in manifest.files}

        self.assertIn("visible/main.py", paths)
        self.assertNotIn(".hidden/secret.py", paths)

    def test_known_excluded_dirs_are_skipped(self) -> None:
        self._write("node_modules/pkg/index.py", "print('skip')")
        self._write("src/app.py", "print('keep')")

        manifest = scan_repository(self.root)
        paths = {item.relative_path.as_posix() for item in manifest.files}

        self.assertIn("src/app.py", paths)
        self.assertNotIn("node_modules/pkg/index.py", paths)

    def test_unsupported_extension_is_excluded(self) -> None:
        self._write("src/main.py", "print('ok')")
        self._write("src/binary.bin", "101010")

        manifest = scan_repository(self.root)
        paths = {item.relative_path.as_posix() for item in manifest.files}

        self.assertIn("src/main.py", paths)
        self.assertNotIn("src/binary.bin", paths)

    def test_large_file_is_excluded_by_size(self) -> None:
        self._write("src/small.py", "print('small')")
        self._write("src/large.py", "x" * 300)

        config = ScannerConfig(max_file_size_bytes=128)
        manifest = scan_repository(self.root, config=config)
        paths = {item.relative_path.as_posix() for item in manifest.files}

        self.assertIn("src/small.py", paths)
        self.assertNotIn("src/large.py", paths)

    def test_classification_counts_source_test_config(self) -> None:
        self._write("src/main.py", "print('source')")
        self._write("tests/test_main.py", "def test_ok():\n    assert True")
        self._write("pyproject.toml", "[project]\nname='gcie'")
        self._write("notes.md", "general notes")

        manifest = scan_repository(self.root)

        self.assertEqual(len(manifest.source_files), 1)
        self.assertEqual(len(manifest.test_files), 1)
        self.assertEqual(len(manifest.config_files), 1)
        self.assertEqual(manifest.total_files, 4)


if __name__ == "__main__":
    unittest.main()
