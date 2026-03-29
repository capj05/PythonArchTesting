"""Escaping utilities for report renderers."""

from __future__ import annotations


def escape_text(value: str) -> str:
    """Text renderer keeps raw value for backward compatibility."""
    return value


def escape_markdown(value: str) -> str:
    """Escape markdown table/control characters."""
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")
