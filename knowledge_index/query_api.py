"""Knowledge index query API."""

from __future__ import annotations

from .models import ClassIndexEntry, FileIndexEntry, FunctionIndexEntry
from .store import InMemoryKnowledgeStore


def find_functions_modifying_variable(store: InMemoryKnowledgeStore, variable: str) -> tuple[FunctionIndexEntry, ...]:
    return tuple(
        fn
        for fn in store.functions.values()
        if variable in fn.variables_written
    )


def find_functions_calling_function(store: InMemoryKnowledgeStore, function_name: str) -> tuple[FunctionIndexEntry, ...]:
    return tuple(
        fn
        for fn in store.functions.values()
        if function_name in fn.functions_called
    )


def find_files_importing_module(store: InMemoryKnowledgeStore, module_name: str) -> tuple[FileIndexEntry, ...]:
    return tuple(
        file
        for file in store.files.values()
        if any(imp == module_name or imp.startswith(f"{module_name}.") for imp in file.imports)
    )


def find_classes_inheriting_from(store: InMemoryKnowledgeStore, base_class: str) -> tuple[ClassIndexEntry, ...]:
    return tuple(
        cls
        for cls in store.classes.values()
        if base_class in cls.base_classes
    )