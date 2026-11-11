"""Editing the text of a module: inserting lines, replacing spans, cutting
a class's bases, and where in a module or function new code goes.
"""

from __future__ import annotations

import ast
import io
import tokenize
from typing import Optional

from pythonarchtesting.util.ast_utils import is_docstring


def _is_future_import(node: ast.stmt) -> bool:
    return isinstance(node, ast.ImportFrom) and node.module == "__future__"


def header_end(tree: ast.Module) -> int:
    """The 0-based line before which a top-level import goes."""
    body = list(tree.body)
    index = 0
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        index = 1
    while index < len(body) and _is_future_import(body[index]):
        index += 1
    if index < len(body):
        node = body[index]
        decorators = getattr(node, "decorator_list", []) or []
        lines = [int(node.lineno), *(int(d.lineno) for d in decorators)]
        return min(lines) - 1
    last = body[-1] if body else None
    return int(getattr(last, "end_lineno", 0) or 0)


def insert(text: str, line: int, new: str) -> str:
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    lines.insert(line, new + "\n")
    return "".join(lines)


def alone(text: str, node: ast.stmt) -> bool:
    """Whether ``node`` has its lines to itself: no header or other statement."""
    lines = text.splitlines()
    first, last = node.lineno - 1, int(node.end_lineno or node.lineno) - 1
    end_col = int(node.end_col_offset or 0)
    before = lines[first][: node.col_offset]
    after = lines[last][end_col:].strip()
    return not before.strip() and (not after or after.startswith("#"))


def function_insert(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[int, int]:
    """Where a statement goes first in ``function``: 0-based line, indentation."""
    body = function.body
    first = body[0]
    if is_docstring(first):
        if len(body) > 1:
            return body[1].lineno - 1, body[1].col_offset
        return int(first.end_lineno or first.lineno), first.col_offset
    return first.lineno - 1, first.col_offset


def replace_span(text: str, node: ast.AST, new: str) -> str:
    lines = text.splitlines(keepends=True)
    row = int(getattr(node, "lineno")) - 1
    start, end = int(getattr(node, "col_offset")), int(getattr(node, "end_col_offset"))
    line = lines[row].encode("utf-8")
    lines[row] = (line[:start] + new.encode("utf-8") + line[end:]).decode("utf-8")
    return "".join(lines)


def replace_spans(text: str, nodes: list[ast.expr], new: str) -> str:
    """``text`` with each one-line node in ``nodes`` replaced by ``new``."""
    lines = text.splitlines(keepends=True)
    for node in sorted(nodes, key=lambda n: (n.lineno, n.col_offset), reverse=True):
        row = node.lineno - 1
        start, end = node.col_offset, int(node.end_col_offset or 0)
        line = lines[row].encode("utf-8")
        lines[row] = (line[:start] + new.encode("utf-8") + line[end:]).decode("utf-8")
    return "".join(lines)


def _base_list(text: str, cls: ast.ClassDef) -> Optional[tuple[int, int]]:
    """Character offsets of the ``(`` of ``cls``'s list of bases and of the
    character after its ``)``; ``None`` when the header has none."""
    lines = text.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))
    first = cls.lineno - 1

    def offset(row: int, col: int) -> int:
        return starts[first + row - 1] + col

    depth = 0
    opened: Optional[int] = None
    tokens = tokenize.generate_tokens(io.StringIO("".join(lines[first:])).readline)
    for token in tokens:
        if token.type != tokenize.OP:
            continue
        if token.string in "([{":
            if depth == 0 and token.string == "(":
                opened = offset(*token.start)
            depth += 1
        elif token.string in ")]}":
            depth -= 1
            if depth == 0 and opened is not None:
                return opened, offset(*token.end)
        elif token.string == ":" and depth == 0:
            return None
    return None


def with_bases(text: str, cls: ast.ClassDef, kept: list[ast.AST]) -> Optional[str]:
    """``text`` with ``cls``'s list of bases and keywords cut down to ``kept``."""
    span = _base_list(text, cls)
    if span is None:
        return None
    parts = [ast.get_source_segment(text, node) for node in kept]
    if any(part is None for part in parts):
        return None
    new = f"({', '.join(str(part) for part in parts)})" if parts else ""
    return text[: span[0]] + new + text[span[1] :]
