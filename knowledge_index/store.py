"""In-memory storage for knowledge index."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import ClassIndexEntry, FileIndexEntry, FunctionIndexEntry


@dataclass(slots=True)
class InMemoryKnowledgeStore:
    functions: dict[str, FunctionIndexEntry] = field(default_factory=dict)
    classes: dict[str, ClassIndexEntry] = field(default_factory=dict)
    files: dict[str, FileIndexEntry] = field(default_factory=dict)

    def add_function(self, entry: FunctionIndexEntry) -> None:
        self.functions[f"{entry.file}::{entry.name}"] = entry

    def add_class(self, entry: ClassIndexEntry) -> None:
        self.classes[f"{entry.file}::{entry.name}"] = entry

    def add_file(self, entry: FileIndexEntry) -> None:
        self.files[entry.path] = entry