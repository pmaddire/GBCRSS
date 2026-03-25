"""Graph storage utilities for incremental workflows."""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx


@dataclass(slots=True)
class GraphStore:
    _snapshots: dict[str, nx.DiGraph]

    def __init__(self) -> None:
        self._snapshots = {}

    def put(self, key: str, graph: nx.DiGraph) -> None:
        self._snapshots[key] = graph.copy()

    def get(self, key: str) -> nx.DiGraph | None:
        graph = self._snapshots.get(key)
        return None if graph is None else graph.copy()

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._snapshots.keys()))