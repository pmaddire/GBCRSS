"""Call resolution utilities for call graph generation."""

from __future__ import annotations

from dataclasses import dataclass

from .models import FunctionEntry, ImportEntry, ModuleParseResult


@dataclass(frozen=True, slots=True)
class ResolvedCall:
    """Resolved function call target."""

    caller: str
    callee: str
    resolved: bool


def _import_alias_map(imports: tuple[ImportEntry, ...]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in imports:
        if entry.module:
            for name in entry.names:
                mapping[name] = f"{entry.module}.{name}"
        else:
            for name in entry.names:
                mapping[name] = name
    return mapping


def resolve_calls(module: ModuleParseResult) -> tuple[ResolvedCall, ...]:
    """Resolve function call strings using local symbols and import aliases."""
    local_funcs = {fn.name for fn in module.functions}
    aliases = _import_alias_map(module.imports)

    resolved_calls: list[ResolvedCall] = []
    for fn in module.functions:
        for called in fn.functions_called:
            if called in local_funcs:
                resolved_calls.append(ResolvedCall(caller=fn.name, callee=called, resolved=True))
                continue

            head = called.split(".", 1)[0]
            if head in aliases:
                tail = called[len(head) + 1 :] if called.startswith(f"{head}.") else ""
                normalized = aliases[head]
                callee = f"{normalized}.{tail}" if tail else normalized
                resolved_calls.append(ResolvedCall(caller=fn.name, callee=callee, resolved=False))
            else:
                resolved_calls.append(ResolvedCall(caller=fn.name, callee=called, resolved=False))

    return tuple(resolved_calls)