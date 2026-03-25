"""Node identity and attribute helpers for graph construction."""

from __future__ import annotations

from pathlib import Path


def file_node_id(path: Path) -> str:
    return f"file:{path.as_posix()}"


def class_node_id(file_path: Path, class_name: str) -> str:
    return f"class:{file_path.as_posix()}::{class_name}"


def function_node_id(file_path: Path, function_name: str) -> str:
    return f"function:{file_path.as_posix()}::{function_name}"


def module_node_id(module_name: str) -> str:
    return f"module:{module_name}"