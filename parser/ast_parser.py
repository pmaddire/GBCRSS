"""AST parser for Python source files."""

from __future__ import annotations

import ast
from pathlib import Path

from .models import (
    AssignmentEntry,
    ClassEntry,
    FunctionEntry,
    ImportEntry,
    ModuleParseResult,
    VariableAccess,
)


class _FunctionAnalyzer(ast.NodeVisitor):
    """Extract variable reads/writes and called function names."""

    def __init__(self) -> None:
        self.reads: set[str] = set()
        self.writes: set[str] = set()
        self.calls: set[str] = set()
        self.accesses: list[VariableAccess] = []

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.reads.add(node.id)
            self.accesses.append(VariableAccess(name=node.id, line=node.lineno, access_type="read"))
        elif isinstance(node.ctx, ast.Store):
            self.writes.add(node.id)
            self.accesses.append(VariableAccess(name=node.id, line=node.lineno, access_type="write"))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        dotted = _attribute_name(node)
        if dotted:
            if isinstance(node.ctx, ast.Load):
                self.reads.add(dotted)
                self.accesses.append(VariableAccess(name=dotted, line=node.lineno, access_type="read"))
            elif isinstance(node.ctx, ast.Store):
                self.writes.add(dotted)
                self.accesses.append(VariableAccess(name=dotted, line=node.lineno, access_type="write"))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_name = _call_name(node.func)
        if call_name:
            self.calls.add(call_name)
        self.generic_visit(node)


class _ClassAnalyzer(ast.NodeVisitor):
    """Extract class-level attributes and method names."""

    def __init__(self) -> None:
        self.attributes: set[str] = set()
        self.methods: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # pragma: no cover - simple dispatch
        self.methods.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # pragma: no cover - simple dispatch
        self.methods.add(node.name)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            for name in _extract_target_names(target):
                self.attributes.add(name)
        self.generic_visit(node)


def _extract_target_names(target: ast.expr) -> list[str]:
    names: list[str] = []
    if isinstance(target, ast.Name):
        names.append(target.id)
    elif isinstance(target, ast.Attribute):
        dotted = _attribute_name(target)
        if dotted:
            names.append(dotted)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            names.extend(_extract_target_names(element))
    return names


def _attribute_name(node: ast.Attribute) -> str:
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return ""


def _annotation_to_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _annotation_to_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        return _annotation_to_name(node.value)
    return ""


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _end_lineno(node: ast.AST) -> int:
    return getattr(node, "end_lineno", getattr(node, "lineno", 0))


def parse_python_source(source: str, file: str | Path = "<memory>") -> ModuleParseResult:
    """Parse Python source into a normalized module parse result."""
    file_path = Path(file)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ModuleParseResult(file=file_path, parse_errors=(str(exc),))

    functions: list[FunctionEntry] = []
    classes: list[ClassEntry] = []
    imports: list[ImportEntry] = []
    assignments: list[AssignmentEntry] = []

    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.append(
                ImportEntry(
                    module="",
                    names=tuple(alias.name for alias in node.names),
                    line=node.lineno,
                )
            )
        elif isinstance(node, ast.ImportFrom):
            imports.append(
                ImportEntry(
                    module=node.module or "",
                    names=tuple(alias.name for alias in node.names),
                    line=node.lineno,
                )
            )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                for name in _extract_target_names(target):
                    assignments.append(AssignmentEntry(target=name, line=node.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            analyzer = _FunctionAnalyzer()
            analyzer.visit(node)

            parameters: list[str] = [arg.arg for arg in node.args.args]
            parameters.extend(arg.arg for arg in node.args.kwonlyargs)
            if node.args.vararg:
                parameters.append(node.args.vararg.arg)
            if node.args.kwarg:
                parameters.append(node.args.kwarg.arg)

            functions.append(
                FunctionEntry(
                    name=node.name,
                    file=file_path,
                    start_line=node.lineno,
                    end_line=_end_lineno(node),
                    parameters=tuple(parameters),
                    variables_read=tuple(sorted(analyzer.reads)),
                    variables_written=tuple(sorted(analyzer.writes)),
                    functions_called=tuple(sorted(analyzer.calls)),
                    docstring=ast.get_docstring(node),
                    accesses=tuple(analyzer.accesses),
                )
            )
        elif isinstance(node, ast.ClassDef):
            class_analyzer = _ClassAnalyzer()
            for body_node in node.body:
                class_analyzer.visit(body_node)

            classes.append(
                ClassEntry(
                    name=node.name,
                    file=file_path,
                    start_line=node.lineno,
                    end_line=_end_lineno(node),
                    methods=tuple(sorted(class_analyzer.methods)),
                    attributes=tuple(sorted(class_analyzer.attributes)),
                    base_classes=tuple(
                        sorted(filter(None, (_annotation_to_name(base) for base in node.bases)))
                    ),
                    docstring=ast.get_docstring(node),
                )
            )

    return ModuleParseResult(
        file=file_path,
        functions=tuple(functions),
        classes=tuple(classes),
        imports=tuple(imports),
        assignments=tuple(assignments),
    )


def parse_python_file(path: str | Path) -> ModuleParseResult:
    """Parse a Python source file from disk."""
    file_path = Path(path)
    source = file_path.read_text(encoding="utf-8")
    return parse_python_source(source, file=file_path)