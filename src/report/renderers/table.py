"""Simple table primitives shared by text and markdown renderers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

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


def render_text_table(table: Table) -> str:
    widths = [len(h) for h in table.headers]
    for row in table.rows:
        for idx, col in enumerate(row):
            widths[idx] = max(widths[idx], len(col))

    def _line(cols: Sequence[str]) -> str:
        return " | ".join(col.ljust(widths[idx]) for idx, col in enumerate(cols))

    sep = "-+-".join("-" * w for w in widths)
    lines: List[str] = [_line(table.headers), sep]
    lines.extend(_line(row) for row in table.rows)
    return "\n".join(lines)
