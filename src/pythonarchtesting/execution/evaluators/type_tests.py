"""Which recorded calls of ``isinstance`` and ``type`` test an object's type.

``forbid_runtime_calls`` sees every call the code makes, but a call of
``isinstance`` or ``type`` is a branch on the type of an object only in some
uses. This module reads the call's line in the target's code and drops only
the calls that plainly are no such branch:

- ``isinstance(x, C)`` when every class it names is a builtin or standard
  library type (``int``, ``str``, ``list``, ``type(None)``, ``ValueError``,
  ``numbers.Number``, ``collections.abc.Mapping``, also imported under
  another name): ``isinstance(x, (int, float))`` or ``isinstance(items,
  list)`` validates input;
- ``type(x)`` that is only displayed: a value of an f-string, an argument of
  ``print``, ``str``, ``repr`` or ``format``, or its ``__name__`` /
  ``__qualname__`` in an f-string or a concatenation, none of them compared
  (``f"{type(x).__name__}"``).

Every other call counts: a class imported under another name, a tuple of
classes kept in a constant, a class held by an attribute, ``type(x)`` kept in
a variable or used as a key. What cannot be read (no file, no call found on
the line) counts too, so nothing is dropped by doubt.
"""

from __future__ import annotations

import ast
import builtins
import collections.abc
import numbers
from pathlib import Path
from typing import Optional

TYPE_TEST_CALLEES = frozenset({"builtins:isinstance", "builtins:type"})
_COMPARING = (ast.Eq, ast.NotEq, ast.Is, ast.IsNot, ast.In, ast.NotIn)
_NAME_ATTRIBUTES = frozenset({"__name__", "__qualname__"})
# Calls that only display what they are given.
_SHOWING = frozenset({"print", "str", "repr", "format"})
# The builtin classes (types and exceptions), by name.
_BUILTIN_TYPES = frozenset(
    name for name, value in vars(builtins).items() if isinstance(value, type)
) | {"NoneType"}
# Standard library modules whose classes a type test of input names, with
# the classes known by name.
_STDLIB_TYPES: dict[str, frozenset[str]] = {
    "builtins": _BUILTIN_TYPES,
    "numbers": frozenset(numbers.__all__),
    "collections.abc": frozenset(collections.abc.__all__),
    "typing": frozenset(collections.abc.__all__) | {"Iterable", "Sequence"},
    "types": frozenset({"NoneType"}),
    "decimal": frozenset({"Decimal"}),
    "fractions": frozenset({"Fraction"}),
    "datetime": frozenset({"date", "datetime", "time", "timedelta"}),
    "pathlib": frozenset({"Path", "PurePath"}),
}
# ``from collections import abc``: the module under the name of its last part.
_STDLIB_TYPES["abc"] = _STDLIB_TYPES["collections.abc"]


class TypeTests:
    """Reads the target's code once per file; one instance per evaluation."""

    def __init__(self, root: Optional[Path]) -> None:
        self._root = root
        self._trees: dict[str, Optional[ast.Module]] = {}
        self._classes: Optional[frozenset[str]] = None

    def project_classes(self) -> frozenset[str]:
        """The names of every class the target's code defines."""
        if self._classes is None:
            names: set[str] = set()
            if self._root is not None:
                for path in sorted(Path(self._root).rglob("*.py")):
                    tree = self._parse(path)
                    if tree is not None:
                        names.update(
                            node.name
                            for node in ast.walk(tree)
                            if isinstance(node, ast.ClassDef)
                        )
            self._classes = frozenset(names)
        return self._classes

    def _parse(self, path: Path) -> Optional[ast.Module]:
        key = str(path)
        if key not in self._trees:
            try:
                self._trees[key] = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
                self._trees[key] = None
        return self._trees[key]

    def is_type_test(self, callee: str, file: object, line: object) -> bool:
        """Whether the call of ``callee`` at ``file``:``line`` tests a type;
        ``True`` when that cannot be read."""
        if callee not in TYPE_TEST_CALLEES or self._root is None:
            return True
        if not isinstance(file, str) or not isinstance(line, int):
            return True
        tree = self._parse(Path(self._root) / file)
        if tree is None:
            return True
        name = callee.partition(":")[2]
        parents = {
            child: node
            for node in ast.walk(tree)
            for child in ast.iter_child_nodes(node)
        }
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
            and node.lineno <= line <= int(node.end_lineno or node.lineno)
        ]
        if not calls:
            return True
        if name == "isinstance":
            imported = _imported(tree)
            return any(self._tests_project_class(call, imported) for call in calls)
        return any(not _displayed(call, parents) for call in calls)

    def _tests_project_class(self, call: ast.Call, imported: dict[str, str]) -> bool:
        if len(call.args) < 2:
            return True
        return not self._known_types(call.args[1], imported)

    def _known_types(self, node: ast.expr, imported: dict[str, str]) -> bool:
        """Whether ``node`` names only builtin or standard library types."""
        if isinstance(node, ast.Tuple):
            return all(self._known_types(element, imported) for element in node.elts)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "type"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value is None
        ):
            return True  # type(None)
        dotted = _dotted(node)
        if dotted is None:
            return False
        head, _, rest = dotted.partition(".")
        if head in imported:
            dotted = imported[head] + (f".{rest}" if rest else "")
        elif not rest:
            return head in _BUILTIN_TYPES and head not in self.project_classes()
        module, _, cls = dotted.rpartition(".")
        return cls in _STDLIB_TYPES.get(module, frozenset())


def _dotted(node: ast.expr) -> Optional[str]:
    """``a.b.c`` for a chain of plain names, else ``None``."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base is not None else None
    return None


def _imported(tree: ast.Module) -> dict[str, str]:
    """Name -> what it stands for, for each name a file imports: ``Number``
    for ``numbers.Number``, ``abc`` for ``collections.abc``; a name imported
    from a project module stands for that (relative) module's name."""
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    found[alias.asname] = alias.name
                else:
                    head = alias.name.partition(".")[0]
                    found.setdefault(head, head)
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            for alias in node.names:
                full = f"{module}.{alias.name}" if module else alias.name
                found[alias.asname or alias.name] = full
    return found


def _decides(node: ast.AST, parent: Optional[ast.AST]) -> bool:
    """Whether the value ``node`` is compared, a subscript key, a ``match``
    subject or the key of a ``.get()``."""
    if isinstance(parent, ast.Compare):
        return any(isinstance(op, _COMPARING) for op in parent.ops)
    if isinstance(parent, ast.Subscript):
        return parent.slice is node
    if isinstance(parent, ast.Match):
        return parent.subject is node
    return (
        isinstance(parent, ast.Call)
        and isinstance(parent.func, ast.Attribute)
        and parent.func.attr == "get"
    )


def _displayed(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> bool:
    """Whether the result of ``type(x)`` is only displayed: a value of an
    f-string, an argument of ``print``/``str``/``repr``/``format``, or its
    name in an f-string or a concatenation, and what shows it is not
    compared (``_decides``)."""
    node: ast.AST = call
    parent = parents.get(node)
    named = False
    if isinstance(parent, ast.Attribute) and parent.attr in _NAME_ATTRIBUTES:
        node, parent, named = parent, parents.get(parent), True
    shown = False
    while True:
        if isinstance(parent, ast.FormattedValue) and parent.value is node:
            node = parents.get(parent, parent)  # the f-string
        elif (
            isinstance(parent, ast.Call)
            and isinstance(parent.func, ast.Name)
            and parent.func.id in _SHOWING
            and node in parent.args
        ):
            if parent.func.id == "print":
                return True
            node = parent
        elif (
            isinstance(parent, ast.BinOp)
            and isinstance(parent.op, ast.Add)
            and (named or shown)
        ):
            node = parent
        else:
            break
        shown = True
        parent = parents.get(node)
    return shown and not _decides(node, parent)


__all__ = ["TYPE_TEST_CALLEES", "TypeTests"]
