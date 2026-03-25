"""Runtime tracing via sys.settrace for execution graph input."""

from __future__ import annotations

import inspect
import sys
import time
from dataclasses import dataclass
from types import FrameType
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """Single runtime trace event."""

    event: str
    function_name: str
    file_path: str
    line_no: int
    timestamp: float


def capture_trace_events(func: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[tuple[TraceEvent, ...], Any, BaseException | None]:
    """Capture call/return/exception events while executing a function."""
    events: list[TraceEvent] = []

    target_code_ids: set[int] = set()
    for _, candidate in inspect.getmembers(sys.modules.get(func.__module__, None), inspect.isfunction):
        if candidate.__module__ == func.__module__:
            target_code_ids.add(id(candidate.__code__))
    target_code_ids.add(id(func.__code__))
    target_file = func.__code__.co_filename

    def tracer(frame: FrameType, event: str, arg: Any):
        in_scope = id(frame.f_code) in target_code_ids or frame.f_code.co_filename == target_file
        if in_scope and event in {"call", "return", "exception"}:
            events.append(
                TraceEvent(
                    event=event,
                    function_name=frame.f_code.co_name,
                    file_path=frame.f_code.co_filename,
                    line_no=frame.f_lineno,
                    timestamp=time.time(),
                )
            )
        return tracer

    previous = sys.gettrace()
    result: Any = None
    caught_error: BaseException | None = None
    sys.settrace(tracer)
    try:
        result = func(*args, **kwargs)
    except BaseException as exc:  # noqa: BLE001
        caught_error = exc
    finally:
        sys.settrace(previous)

    return tuple(events), result, caught_error