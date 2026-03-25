"""Phase 7 git miner tests."""

from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path

from git import Repo

from git_integration.git_miner import mine_commit_history


class GitMinerTests(unittest.TestCase):
    def _init_repo(self, root: Path) -> Repo:
        repo = Repo.init(root)
        with repo.config_writer() as cw:
            cw.set_value("user", "name", "GCIE Test")
            cw.set_value("user", "email", "gcie@example.com")
        return repo

    def test_mines_commit_metadata_and_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = self._init_repo(root)
            try:
                (root / "a.py").write_text("print('a')\n", encoding="utf-8")
                repo.index.add(["a.py"])
                repo.index.commit("add a")

                records = mine_commit_history(root)
                self.assertGreaterEqual(len(records), 1)
                self.assertTrue(any(change.path == "a.py" for change in records[0].files))
            finally:
                repo.git.clear_cache()
                repo.close()
                del repo
                gc.collect()

    def test_handles_rename_and_author_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = self._init_repo(root)
            try:
                (root / "old.py").write_text("print('x')\n", encoding="utf-8")
                repo.index.add(["old.py"])
                repo.index.commit("add old")

                repo.git.mv("old.py", "new.py")
                repo.index.commit("rename old to new")

                records = mine_commit_history(root, max_count=2)
                self.assertEqual(len(records), 2)
                self.assertTrue(all(record.author for record in records))
                changed_paths = {change.path for record in records for change in record.files}
                self.assertIn("new.py", changed_paths)
            finally:
                repo.git.clear_cache()
                repo.close()
                del repo
                gc.collect()

    def test_empty_history_returns_no_records(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = self._init_repo(root)
            try:
                records = mine_commit_history(root)
                self.assertEqual(records, ())
            finally:
                repo.git.clear_cache()
                repo.close()
                del repo
                gc.collect()


if __name__ == "__main__":
    unittest.main()