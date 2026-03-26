"""Ranking utilities for hybrid retrieval."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HybridScore:
    node_id: str
    score: float
    symbolic_distance: int | None
    semantic_score: float | None
    git_recency: float | None
    coverage_risk: float | None
    lexical_overlap: int = 0
    path_relevance: float = 0.0
    semantic_hits: int = 0


def combine_score(
    *,
    symbolic_distance: int | None,
    semantic_score: float | None,
    git_recency: float | None,
    coverage_risk: float | None,
    w_symbolic: float = 0.4,
    w_semantic: float = 0.3,
    w_git: float = 0.2,
    w_coverage: float = 0.1,
) -> float:
    """Combine component signals into a single hybrid score."""
    symbolic_component = 0.0 if symbolic_distance is None else (1.0 / (1.0 + float(symbolic_distance)))
    semantic_component = 0.0 if semantic_score is None else float(semantic_score)
    git_component = 0.0 if git_recency is None else float(git_recency)
    coverage_component = 0.0 if coverage_risk is None else float(coverage_risk)

    return (
        w_symbolic * symbolic_component
        + w_semantic * semantic_component
        + w_git * git_component
        + w_coverage * coverage_component
    )
