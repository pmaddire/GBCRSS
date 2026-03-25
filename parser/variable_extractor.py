"""Variable dependency extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass

from .models import FunctionEntry, ModuleParseResult


@dataclass(frozen=True, slots=True)
class VariableDependency:
    """Represents variable usage by a function."""

    function_name: str
    variable_name: str
    access_type: str  # READS | WRITES | MODIFIES


def extract_variable_dependencies(module: ModuleParseResult) -> tuple[VariableDependency, ...]:
    """Extract variable read/write/modifies relationships from parsed functions."""
    out: list[VariableDependency] = []

    for fn in module.functions:
        for name in sorted(set(fn.variables_read)):
            out.append(VariableDependency(function_name=fn.name, variable_name=name, access_type="READS"))

        for name in sorted(set(fn.variables_written)):
            out.append(VariableDependency(function_name=fn.name, variable_name=name, access_type="WRITES"))
            out.append(VariableDependency(function_name=fn.name, variable_name=name, access_type="MODIFIES"))

    return tuple(out)