"""Parser package for GCIE."""

from .ast_parser import parse_python_file
from .models import (
    ClassEntry,
    FunctionEntry,
    ModuleParseResult,
    VariableAccess,
)

__all__ = [
    "ClassEntry",
    "FunctionEntry",
    "ModuleParseResult",
    "VariableAccess",
    "parse_python_file",
]

