"""Parse GCIE-managed architecture files."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Subsystem:
    name: str
    purpose: str = ""
    status: str = ""
    key_files: list[str] | None = None
    interfaces: list[str] | None = None
    depends_on: list[str] | None = None
    used_by: list[str] | None = None
    failure_modes: list[str] | None = None
    notes: list[str] | None = None


@dataclass
class ArchitectureDoc:
    project_summary: str = ""
    system_stage: str = ""
    global_constraints: str = ""
    subsystems: list[Subsystem] | None = None
    data_flow: str = ""
    entry_points: str = ""
    active_work_areas: str = ""
    known_risks: str = ""


_LIST_FIELDS = {
    "Key Files": "key_files",
    "Interfaces": "interfaces",
    "Depends On": "depends_on",
    "Used By": "used_by",
    "Failure Modes": "failure_modes",
    "Notes": "notes",
}

_REQUIRED_SECTIONS = {
    "Project Summary",
    "System Stage",
    "Global Constraints",
    "Subsystems",
    "Data Flow",
    "Entry Points",
    "Active Work Areas",
    "Known Risks",
}


class ArchitectureParseError(ValueError):
    """Raised when a GCIE architecture document is malformed."""


def parse_architecture(text: str) -> ArchitectureDoc:
    """Parse a GCIE architecture.md file into a structured object.

    Raises ArchitectureParseError when required sections are missing.
    """
    lines = text.splitlines()

    if not lines or not lines[0].strip().startswith("# GCIE Architecture"):
        raise ArchitectureParseError("missing_header")

    subsystems: list[Subsystem] = []

    project_summary = ""
    system_stage = ""
    global_constraints = ""
    data_flow = ""
    entry_points = ""
    active_work_areas = ""
    known_risks = ""

    seen_sections: set[str] = set()
    current_section = ""
    current_subsystem: Subsystem | None = None
    current_list_field: str | None = None
    buffer: list[str] = []

    def flush_section() -> str:
        content = "\n".join(line.strip() for line in buffer if line.strip())
        buffer.clear()
        return content

    def commit_subsystem() -> None:
        nonlocal current_subsystem
        if current_subsystem is not None:
            subsystems.append(current_subsystem)
        current_subsystem = None

    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_subsystem is None and current_section:
                content = flush_section()
                if current_section == "Project Summary":
                    project_summary = content
                elif current_section == "System Stage":
                    system_stage = content
                elif current_section == "Global Constraints":
                    global_constraints = content
                elif current_section == "Data Flow":
                    data_flow = content
                elif current_section == "Entry Points":
                    entry_points = content
                elif current_section == "Active Work Areas":
                    active_work_areas = content
                elif current_section == "Known Risks":
                    known_risks = content
            current_section = stripped[len("## ") :]
            seen_sections.add(current_section)
            current_list_field = None
            continue

        if stripped.startswith("### Subsystem:"):
            commit_subsystem()
            name = stripped.split(":", 1)[1].strip()
            if not name:
                raise ArchitectureParseError("subsystem_missing_name")
            current_subsystem = Subsystem(name=name)
            current_list_field = None
            continue

        if current_subsystem is not None:
            if stripped.endswith(":") and stripped[:-1] in _LIST_FIELDS:
                current_list_field = _LIST_FIELDS[stripped[:-1]]
                setattr(current_subsystem, current_list_field, [])
                continue

            if stripped.startswith("Purpose:"):
                current_subsystem.purpose = stripped.split(":", 1)[1].strip()
                current_list_field = None
                continue

            if stripped.startswith("Status:"):
                current_subsystem.status = stripped.split(":", 1)[1].strip()
                current_list_field = None
                continue

            if stripped.startswith("-") and current_list_field:
                value = stripped.lstrip("- ").strip()
                if value:
                    target = getattr(current_subsystem, current_list_field)
                    if target is not None:
                        target.append(value)
                continue

        if current_section and current_subsystem is None:
            buffer.append(line)

    commit_subsystem()

    missing_sections = _REQUIRED_SECTIONS - seen_sections
    if missing_sections:
        raise ArchitectureParseError("missing_sections")

    return ArchitectureDoc(
        project_summary=project_summary,
        system_stage=system_stage,
        global_constraints=global_constraints,
        subsystems=subsystems,
        data_flow=data_flow,
        entry_points=entry_points,
        active_work_areas=active_work_areas,
        known_risks=known_risks,
    )
