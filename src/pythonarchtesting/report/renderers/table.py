"""Simple table primitives shared by text and markdown renderers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .escape import escape_markdown


@dataclass(frozen=True, slots=True)
class Table:
    """Tabular data representation."""

    headers: Tuple[str, ...]
    rows: Tuple[Tuple[str, ...], ...]


def render_markdown_table(table: Table) -> str:
    header = "| " + " | ".join(escape_markdown(h) for h in table.headers) + " |"
    sep = "|" + "|".join("---" for _ in table.headers) + "|"
    rows: List[str] = [header, sep]
    for row in table.rows:
        rows.append("| " + " | ".join(escape_markdown(v) for v in row) + " |")
    return "\n".join(rows)
