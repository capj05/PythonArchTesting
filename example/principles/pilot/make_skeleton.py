"""Write the code skeleton of a principle's task from its model solution.

``example/principles/<p>/reference/`` -> ``example/principles/pilot/<p>/skeleton/``:

- the ``__archtest__: ...`` statements and the ``pythonarchtesting`` imports go,
  and so do the names imported from ``typing`` that nothing uses any more
  (``Annotated``);
- module and package docstrings go: the reference's describe how it is checked;
- every function and method body becomes its docstring (if it had one) plus
  ``raise NotImplementedError``;
- signatures, decorators, classes, function and class docstrings, module
  constants and the other imports stay as written. Comments outside the kept
  lines go (the reference's comments describe its markers).

The output is deterministic (two runs give the same bytes) and importable. It
fails when a skeleton still mentions any of ``_FORBIDDEN`` (case ignored): the
words that tell how solutions are checked.

Usage, from the repository root::

    python example/principles/pilot/make_skeleton.py io_separation encapsulation
"""

from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOGUE = HERE.parent
_FORBIDDEN = ("__archtest__", "pythonarchtesting", "archtest", "marker", "model solution", "never compared")
_TYPING = ("typing", "typing_extensions")


def _segment(lines: list[str], node: ast.AST) -> list[str]:
    """The node's source lines, the first one cut at the node's column."""
    first, last = node.lineno - 1, node.end_lineno  # type: ignore[attr-defined]
    chunk = lines[first:last]
    chunk[-1] = chunk[-1][: node.end_col_offset]  # type: ignore[attr-defined]
    chunk[0] = chunk[0][node.col_offset :]  # type: ignore[attr-defined]
    return chunk


def _indented(lines: list[str], node: ast.AST, indent: int) -> list[str]:
    chunk = _segment(lines, node)
    return [" " * indent + chunk[0]] + chunk[1:]


def _is_archtest(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "__archtest__"
    )


def _is_tool_import(node: ast.stmt) -> bool:
    if isinstance(node, ast.Import):
        return all(alias.name.split(".")[0] == "pythonarchtesting" for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "").split(".")[0] == "pythonarchtesting"
    return False


def _docstring(node: ast.AST) -> ast.Expr | None:
    body = getattr(node, "body", [])
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            return body[0]
    return None


def _header(lines: list[str], node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
    """Decorators and the ``def`` / ``class`` line(s), up to the colon."""
    start = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
    body = node.body[0]
    # The last line before the body that ends with the colon; comment and blank
    # lines between the header and the body are not part of it.
    for index in range(body.lineno - 2, node.lineno - 2, -1):
        if _ends_header(lines[index]):
            return lines[start : index + 1]
    # The body starts on the header's last line: ``def f(): ...``.
    chunk = lines[start : body.lineno]
    chunk[-1] = chunk[-1][: body.col_offset].rstrip()
    return chunk


def _ends_header(line: str) -> bool:
    code = line.split("#", 1)[0].rstrip()
    return code.endswith(":")


def _body_indent(node: ast.AST) -> int:
    body = node.body[0]  # type: ignore[attr-defined]
    if body.lineno == node.lineno or body.lineno == node.end_lineno:  # type: ignore[attr-defined]
        return node.col_offset + 4  # type: ignore[attr-defined]
    return body.col_offset


def _function(lines: list[str], node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    out = _header(lines, node)
    indent = _body_indent(node)
    doc = _docstring(node)
    if doc is not None:
        out += _indented(lines, doc, indent)
    out.append(" " * indent + "raise NotImplementedError")
    return out


def _block(lines: list[str], body: list[ast.stmt], indent: int, top: bool) -> list[str]:
    """The kept statements of a module or class body, with blank lines between."""
    out: list[str] = []
    previous: ast.stmt | None = None
    for node in body:
        if _is_archtest(node) or _is_tool_import(node):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chunk = _function(lines, node)
        elif isinstance(node, ast.ClassDef):
            chunk = _header(lines, node)
            inner = _block(lines, node.body, _body_indent(node), top=False)
            chunk += inner or [" " * _body_indent(node) + "pass"]
        else:
            chunk = _indented(lines, node, indent)
        if previous is not None:
            defs = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            if isinstance(node, defs) or isinstance(previous, defs):
                out += [""] * (2 if top else 1)
            elif node.lineno > previous.end_lineno + 1:  # type: ignore[operator]
                out.append("")
        out += chunk
        previous = node
    return out


def _drop_unused_typing(text: str) -> str:
    """Remove the names imported from ``typing`` that the module no longer uses."""
    tree = ast.parse(text)
    used = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {
        node.value.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
    }
    lines = text.splitlines()
    for node in reversed(tree.body):
        if not (isinstance(node, ast.ImportFrom) and node.module in _TYPING):
            continue
        kept = [alias for alias in node.names if (alias.asname or alias.name) in used]
        if len(kept) == len(node.names):
            continue
        start, end = node.lineno - 1, node.end_lineno
        replacement = [ast.unparse(ast.ImportFrom(module=node.module, names=kept, level=0))] if kept else []
        lines[start:end] = replacement  # type: ignore[index]
        if not kept and start < len(lines) and start > 0 and not lines[start].strip() and not lines[start - 1].strip():
            del lines[start]
    return "\n".join(lines) + "\n"


def skeleton_of(source: str) -> str:
    lines = source.splitlines()
    tree = ast.parse(source)
    body = tree.body[1:] if _docstring(tree) is not None else tree.body
    text = "\n".join(_block(lines, body, 0, top=True)) + "\n"
    text = _drop_unused_typing(text)
    while "\n\n\n\n" in text:
        text = text.replace("\n\n\n\n", "\n\n\n")
    return text.lstrip("\n")


def make(principle: str, catalogue: Path = CATALOGUE, out_base: Path = HERE) -> Path:
    reference = catalogue / principle / "reference"
    if not reference.is_dir():
        raise SystemExit(f"{reference} is missing")
    destination = out_base / principle / "skeleton"
    if destination.exists():
        shutil.rmtree(destination)
    for path in sorted(reference.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = skeleton_of(path.read_text(encoding="utf-8"))
        leaked = [word for word in _FORBIDDEN if word in text.lower()]
        if leaked:
            raise SystemExit(f"{path}: the skeleton still mentions {', '.join(leaked)}")
        target = destination / path.relative_to(reference)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return destination


def main(argv: list[str]) -> int:
    if not argv:
        raise SystemExit(__doc__)
    for principle in argv:
        print(f"wrote {make(principle).relative_to(CATALOGUE.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
