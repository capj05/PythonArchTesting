"""Shared renderer helpers for deterministic output across formats."""

from __future__ import annotations

from typing import Any, Dict


def format_entity(entity: Dict[str, Any]) -> str:
    """Format entity as module:qualname label."""
    module = entity.get("module") or ""
    qualname = entity.get("qualname") or ""
    if module and qualname:
        return f"{module}:{qualname}"
    return module or qualname or ""


def format_location(source: Dict[str, Any]) -> str:
    """Format file:line location from source dictionary."""
    file_value = source.get("file")
    line_value = source.get("line")
    if file_value and line_value is not None:
        return f"{file_value}:{line_value}"
    if file_value:
        return str(file_value)
    return ""
