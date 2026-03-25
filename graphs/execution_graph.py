"""Execution trace graph builder."""

from __future__ import annotations

from typing import Iterable

import networkx as nx

from tracing.runtime_tracer import TraceEvent


def build_execution_graph(events: Iterable[TraceEvent]) -> nx.DiGraph:
    """Build ordered runtime execution graph from trace events."""
    graph = nx.DiGraph()
    ordered = list(events)

    for idx, event in enumerate(ordered):
        node_id = f"event:{idx}:{event.function_name}:{event.event}"
        graph.add_node(
            node_id,
            type="execution_event",
            label=f"{event.function_name}:{event.event}",
            function=event.function_name,
            event=event.event,
            file=event.file_path,
            line=event.line_no,
            timestamp=event.timestamp,
            order=idx,
        )

        if idx > 0:
            prev = f"event:{idx - 1}:{ordered[idx - 1].function_name}:{ordered[idx - 1].event}"
            graph.add_edge(prev, node_id, type="EXECUTES")

    return graph