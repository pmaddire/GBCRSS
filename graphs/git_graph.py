"""Git history graph builder."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import networkx as nx

from git_integration.git_miner import CommitRecord


def _commit_node_id(hexsha: str) -> str:
    return f"commit:{hexsha}"


def _file_node_id(path: str) -> str:
    return f"file:{Path(path).as_posix()}"


def build_git_graph(records: Iterable[CommitRecord]) -> nx.DiGraph:
    """Build commit-file change graph using CHANGED_IN edges."""
    graph = nx.DiGraph()

    for record in records:
        commit_id = _commit_node_id(record.hexsha)
        graph.add_node(
            commit_id,
            type="commit",
            label=record.hexsha[:10],
            author=record.author,
            committed_date=record.committed_date,
            summary=record.summary,
        )

        for change in record.files:
            if not change.path:
                continue
            file_id = _file_node_id(change.path)
            graph.add_node(file_id, type="file", label=Path(change.path).as_posix(), path=Path(change.path).as_posix())
            graph.add_edge(file_id, commit_id, type="CHANGED_IN", change_type=change.change_type)

    return graph