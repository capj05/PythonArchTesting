from __future__ import annotations

from pathlib import Path


class ToolInputError(ValueError):
    """Bad tool input; the message reaches the MCP client as the tool error."""


def require_absolute(path: str, name: str) -> Path:
    """Return ``path`` as a ``Path``, rejecting relative paths."""
    resolved = Path(path)
    if not resolved.is_absolute():
        raise ToolInputError(f"{name} must be an absolute path: {path}")
    return resolved
