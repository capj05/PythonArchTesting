from __future__ import annotations

import difflib
import site
import sys
from pathlib import Path
from typing import Any, Optional

from pythonarchtesting.mcp_server.errors import ToolInputError

_CATEGORY_PREFIX = "- **Category:** "
_PLACEMENT_PREFIX = "- **Placement:** "
_DYNAMIC_MARKER = "**Runs only with:**"
_NOT_FOUND = "marker documentation not found; reinstall pythonarchtesting[mcp]"


def marker_docs_dir() -> Path:
    """Locate the marker docs: the checkout first, then the wheel's data dir (system, then user)."""
    candidates = (
        Path(__file__).parents[3] / "docs" / "markers",
        Path(sys.prefix) / "share" / "pythonarchtesting" / "markers",
        Path(site.getuserbase()) / "share" / "pythonarchtesting" / "markers",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise ToolInputError(_NOT_FOUND)


def _doc_paths() -> list[Path]:
    return sorted(
        path for path in marker_docs_dir().glob("*.md") if path.stem != "README"
    )


def _field(text: str, prefix: str) -> str:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def _summary(text: str) -> str:
    lines = text.splitlines()
    title = next((i for i, line in enumerate(lines) if line.startswith("# ")), -1)
    paragraph: list[str] = []
    for line in lines[title + 1 :]:
        if line.strip():
            paragraph.append(line.strip())
        elif paragraph:
            break
    return " ".join(paragraph)


def _entry(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return {
        "name": path.stem,
        "category": _field(text, _CATEGORY_PREFIX),
        "placement": _field(text, _PLACEMENT_PREFIX),
        "requires_dynamic": _DYNAMIC_MARKER in text,
        "summary": _summary(text),
    }


def list_markers(category: Optional[str] = None) -> list[dict[str, Any]]:
    """List every marker, optionally restricted to one category (case-insensitive)."""
    entries = [_entry(path) for path in _doc_paths()]
    if category is None:
        return entries
    wanted = category.casefold()
    selected = [e for e in entries if e["category"].casefold() == wanted]
    if not selected:
        known = ", ".join(sorted({e["category"] for e in entries}))
        raise ToolInputError(
            f"unknown category {category!r}; known categories: {known}"
        )
    return selected


def describe_marker(name: str) -> dict[str, Any]:
    """Return one marker's metadata and its full documentation text."""
    paths = {path.stem: path for path in _doc_paths()}
    if name not in paths:
        close = difflib.get_close_matches(name, list(paths), n=3)
        hint = f"; did you mean: {', '.join(close)}" if close else ""
        raise ToolInputError(f"unknown marker {name!r}{hint}")
    entry = _entry(paths[name])
    return {
        "name": name,
        "category": entry["category"],
        "placement": entry["placement"],
        "requires_dynamic": entry["requires_dynamic"],
        "markdown": paths[name].read_text(encoding="utf-8"),
    }
