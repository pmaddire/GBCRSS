"""Knowledge index data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FunctionIndexEntry:
    name: str
    file: str
    start_line: int
    end_line: int
    parameters: tuple[str, ...]
    variables_read: tuple[str, ...]
    variables_written: tuple[str, ...]
    functions_called: tuple[str, ...]
    docstring: str | None


@dataclass(frozen=True, slots=True)
class ClassIndexEntry:
    name: str
    file: str
    methods: tuple[str, ...]
    attributes: tuple[str, ...]
    base_classes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FileIndexEntry:
    path: str
    imports: tuple[str, ...]
    classes_defined: tuple[str, ...]
    functions_defined: tuple[str, ...]