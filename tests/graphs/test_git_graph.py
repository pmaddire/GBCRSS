"""Phase 7 git graph tests."""

from __future__ import annotations

import unittest

from git_integration.git_miner import CommitRecord, FileChange
from graphs.git_graph import build_git_graph


class GitGraphTests(unittest.TestCase):
    def test_builds_commit_file_changed_in_edges(self) -> None:
        records = (
            CommitRecord(
                hexsha="abc123",
                author="Dev",
                committed_date=123,
                summary="msg",
                files=(FileChange(path="src/app.py", change_type="M"),),
            ),
        )
        graph = build_git_graph(records)

        self.assertIn("commit:abc123", graph.nodes)
        self.assertIn("file:src/app.py", graph.nodes)
        self.assertIn(("file:src/app.py", "commit:abc123"), graph.edges)

        edge = graph.get_edge_data("file:src/app.py", "commit:abc123")
        self.assertEqual(edge["type"], "CHANGED_IN")
        self.assertEqual(edge["change_type"], "M")


if __name__ == "__main__":
    unittest.main()