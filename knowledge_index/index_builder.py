"""Build knowledge index from parsed modules."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from parser.models import ModuleParseResult

from .models import ClassIndexEntry, FileIndexEntry, FunctionIndexEntry
from .store import InMemoryKnowledgeStore


def build_knowledge_index(modules: Iterable[ModuleParseResult]) -> InMemoryKnowledgeStore:
    """Build in-memory knowledge index from parse outputs."""
    store = InMemoryKnowledgeStore()

    for module in modules:
        file_path = Path(module.file).as_posix()
        imports = tuple(sorted({
            f"{imp.module}.{name}" if imp.module else name
            for imp in module.imports
            for name in (imp.names or ())
        }))

        file_entry = FileIndexEntry(
            path=file_path,
            imports=imports,
            classes_defined=tuple(sorted(cls.name for cls in module.classes)),
            functions_defined=tuple(sorted(fn.name for fn in module.functions)),
        )
        store.add_file(file_entry)

        for cls in module.classes:
            store.add_class(
                ClassIndexEntry(
                    name=cls.name,
                    file=file_path,
                    methods=cls.methods,
                    attributes=cls.attributes,
                    base_classes=cls.base_classes,
                )
            )

        for fn in module.functions:
            store.add_function(
                FunctionIndexEntry(
                    name=fn.name,
                    file=file_path,
                    start_line=fn.start_line,
                    end_line=fn.end_line,
                    parameters=fn.parameters,
                    variables_read=fn.variables_read,
                    variables_written=fn.variables_written,
                    functions_called=fn.functions_called,
                    docstring=fn.docstring,
                )
            )

    return store