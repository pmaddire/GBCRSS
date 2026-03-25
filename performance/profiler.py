"""Simple performance profiling utilities."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ProfileResult:
    label: str
    duration_ms: float


def profile_call(label: str, fn: Callable[..., T], *args, **kwargs) -> tuple[T, ProfileResult]:
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    end = time.perf_counter()
    return result, ProfileResult(label=label, duration_ms=(end - start) * 1000.0)