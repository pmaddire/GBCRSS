"""Evaluate whether to fall back to normal context."""

from __future__ import annotations

from .architecture_slicer import ArchitectureSliceResult


def should_fallback(result: ArchitectureSliceResult, config: dict) -> tuple[bool, str | None]:
    """Decide whether architecture slicing is insufficient."""
    if result.error:
        return True, result.error

    if not result.snippets:
        return True, "no_snippets"

    threshold = float(config.get("confidence_threshold", 0.2))
    if result.confidence < threshold:
        if config.get("fallback_to_normal_on_low_confidence", True):
            return True, "low_confidence"

    return False, None
