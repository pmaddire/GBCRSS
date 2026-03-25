"""Intermediate representation models emitted by the parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VariableAccess:
    """Represents a variable read/write access in function scope."""

    name: str
    line: int
    access_type: str  # "read" | "write"


@dataclass(frozen=True, slots=True)
class FunctionEntry:
    """Represents parsed metadata for a function."""

    name: str
    file: Path
    start_line: int
    end_line: int
    parameters: tuple[str, ...]
    variables_read: tuple[str, ...]
    variables_written: tuple[str, ...]
    functions_called: tuple[str, ...]
    docstring: str | None
    accesses: tuple[VariableAccess, ...] = ()


@dataclass(frozen=True, slots=True)
class ClassEntry:
    """Represents parsed metadata for a class."""

    name: str
    file: Path
    start_line: int
    end_line: int
    methods: tuple[str, ...]
    attributes: tuple[str, ...]
    base_classes: tuple[str, ...]
    docstring: str | None


@dataclass(frozen=True, slots=True)
class ImportEntry:
    """Represents an import statement."""

    module: str
    names: tuple[str, ...]
    line: int


@dataclass(frozen=True, slots=True)
class AssignmentEntry:
    """Represents an assignment target at module scope."""

    target: str
    line: int


@dataclass(slots=True)
class ModuleParseResult:
    """Top-level parse result for a Python module."""

    file: Path
    functions: tuple[FunctionEntry, ...] = ()
    classes: tuple[ClassEntry, ...] = ()
    imports: tuple[ImportEntry, ...] = ()
    assignments: tuple[AssignmentEntry, ...] = ()
    parse_errors: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)