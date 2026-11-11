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
  An exception class of any module (a name ending in ``Error`` or
  ``Exception``, or a project class derived from an exception) and a
  ``typing`` alias (``typing.List``) count as such types too, and so does a
  union of them (``int | float``);
- ``type(x)`` that is only displayed: a value of an f-string, an argument of
  ``print``, ``str``, ``repr`` or ``format``, of ``.format()`` or of a logging
  call (``log.warning(...)``, ``logging.error(...)``), the right side of a
  ``%`` whose left side is a string, or its ``__name__`` / ``__qualname__`` in
  an f-string or a concatenation, none of them compared
  (``f"{type(x).__name__}"``);
- ``type(None)`` (the class of ``None``), ``type(x)`` handed to
  ``isinstance`` or ``issubclass`` (the call of those is judged instead) and
  ``type(x)(...)``, which builds an object of the same class.

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

from pythonarchtesting.constants import FileConstants
from pythonarchtesting.util import ast_utils

TYPE_TEST_CALLEES = frozenset({"builtins:isinstance", "builtins:type"})
_COMPARING = (ast.Eq, ast.NotEq, ast.Is, ast.IsNot, ast.In, ast.NotIn)
_NAME_ATTRIBUTES = frozenset({"__name__", "__qualname__"})
# Calls that only display what they are given.
_SHOWING = frozenset({"print", "str", "repr", "format"})
# Methods of a logger (``log.warning``, ``logging.error``): they display
# their arguments and return nothing.
_LOGGING = frozenset(
    {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
)
# Calls that take a class as an argument: ``type(x)`` given to them is no
# test of its own.
_CLASS_TAKING = frozenset({"isinstance", "issubclass"})
# Name endings of exception classes in any module.
_EXCEPTION_SUFFIXES = ("Error", "Exception")
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


def _python_files(root: Path) -> list[Path]:
    """The ``.py`` files under ``root``, sorted, none in a hidden directory,
    ``__pycache__`` or a virtual environment (``FileConstants.EXCLUDED_DIRS``)."""
    return [
        path
        for path in sorted(root.rglob("*.py"))
        if not any(
            part.startswith(".") or part in FileConstants.EXCLUDED_DIRS
            for part in path.relative_to(root).parts[:-1]
        )
    ]


class TypeTests:
    """Reads the target's code once per file; one instance per evaluation."""

    def __init__(self, root: Optional[Path]) -> None:
        self._root = root
        self._trees: dict[str, Optional[ast.Module]] = {}
        self._classes: Optional[frozenset[str]] = None
        self._exceptions: Optional[frozenset[str]] = None
        # Per file: each node's parent, the calls of a plain name in the
        # order ``ast.walk`` meets them, and what the file imports.
        self._parents: dict[str, dict[ast.AST, ast.AST]] = {}
        self._calls: dict[str, dict[str, list[ast.Call]]] = {}
        self._imports: dict[str, dict[str, str]] = {}
        self._answers: dict[tuple[str, str, int], bool] = {}

    def project_classes(self) -> frozenset[str]:
        """The names of every class the target's code defines."""
        if self._classes is None:
            names: set[str] = set()
            if self._root is not None:
                for path in _python_files(Path(self._root)):
                    tree = self._parse(path)
                    if tree is not None:
                        names.update(
                            node.name
                            for node in ast.walk(tree)
                            if isinstance(node, ast.ClassDef)
                        )
            self._classes = frozenset(names)
        return self._classes

    def project_exceptions(self) -> frozenset[str]:
        """The names of the target's classes derived (by the names of their
        bases) from a builtin exception or another such class."""
        if self._exceptions is None:
            bases: dict[str, set[str]] = {}
            if self._root is not None:
                for path in _python_files(Path(self._root)):
                    tree = self._parse(path)
                    for node in ast.walk(tree) if tree is not None else ():
                        if isinstance(node, ast.ClassDef):
                            bases.setdefault(node.name, set()).update(
                                (ast_utils.dotted(b) or "").rpartition(".")[2]
                                for b in node.bases
                            )
            found = {
                name
                for name in _BUILTIN_TYPES
                if isinstance(getattr(builtins, name, None), type)
                and issubclass(getattr(builtins, name), BaseException)
            }
            grown = True
            while grown:
                new = {name for name, of in bases.items() if of & found} - found
                found |= new
                grown = bool(new)
            self._exceptions = frozenset(found & set(bases))
        return self._exceptions

    def _parse(self, path: Path) -> Optional[ast.Module]:
        key = str(path)
        if key not in self._trees:
            try:
                # From bytes, as Python reads a module: a BOM or a coding
                # line holds; a file that does not decode is a SyntaxError.
                self._trees[key] = ast.parse(path.read_bytes())
            except (OSError, SyntaxError, ValueError):
                self._trees[key] = None
        return self._trees[key]

    def is_type_test(self, callee: str, file: object, line: object) -> bool:
        """Whether the call of ``callee`` at ``file``:``line`` tests a type;
        ``True`` when that cannot be read."""
        if callee not in TYPE_TEST_CALLEES or self._root is None:
            return True
        if not isinstance(file, str) or not isinstance(line, int):
            return True
        key = (callee, file, line)
        if key not in self._answers:
            self._answers[key] = self._reads_as_type_test(callee, file, line)
        return self._answers[key]

    def _reads_as_type_test(self, callee: str, file: str, line: int) -> bool:
        path = Path(str(self._root)) / file
        tree = self._parse(path)
        if tree is None:
            return True
        name = callee.partition(":")[2]
        key = str(path)
        if key not in self._calls:
            named: dict[str, list[ast.Call]] = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    named.setdefault(node.func.id, []).append(node)
            self._calls[key] = named
        calls = [
            node
            for node in self._calls[key].get(name, [])
            if node.lineno <= line <= int(node.end_lineno or node.lineno)
        ]
        if not calls:
            return True
        if name == "isinstance":
            if key not in self._imports:
                self._imports[key] = _imported(tree)
            imported = self._imports[key]
            return any(self._tests_project_class(call, imported) for call in calls)
        if key not in self._parents:
            self._parents[key] = {
                child: node
                for node in ast.walk(tree)
                for child in ast.iter_child_nodes(node)
            }
        parents = self._parents[key]
        return any(
            not (_no_test_of_its_own(call, parents) or _displayed(call, parents))
            for call in calls
        )

    def _tests_project_class(self, call: ast.Call, imported: dict[str, str]) -> bool:
        if len(call.args) < 2:
            return True
        return not self._known_types(call.args[1], imported)

    def _known_types(self, node: ast.expr, imported: dict[str, str]) -> bool:
        """Whether ``node`` names only builtin or standard library types."""
        if isinstance(node, ast.Tuple):
            return all(self._known_types(element, imported) for element in node.elts)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return self._known_types(node.left, imported) and self._known_types(
                node.right, imported
            )  # int | float
        if isinstance(node, ast.Call):
            return _none_type(node)  # type(None)
        dotted = ast_utils.dotted(node)
        if dotted is None:
            return False
        if dotted.rpartition(".")[2] in self.project_exceptions() or dotted.endswith(
            _EXCEPTION_SUFFIXES
        ):
            return True  # handling an error, not branching on a kind
        head, _, rest = dotted.partition(".")
        if head in imported:
            dotted = imported[head] + (f".{rest}" if rest else "")
        elif not rest:
            return head in _BUILTIN_TYPES and head not in self.project_classes()
        module, _, cls = dotted.rpartition(".")
        if module in _TYPING_MODULES:
            return True  # typing.List and the other aliases
        return cls in _STDLIB_TYPES.get(module, frozenset())


# Modules whose every name is a type alias.
_TYPING_MODULES = frozenset({"typing", "typing_extensions"})


def _none_type(call: ast.Call) -> bool:
    """Whether ``call`` is ``type(None)``."""
    return (
        isinstance(call.func, ast.Name)
        and call.func.id == "type"
        and len(call.args) == 1
        and not call.keywords
        and isinstance(call.args[0], ast.Constant)
        and call.args[0].value is None
    )


def _no_test_of_its_own(call: ast.Call, parents: dict[ast.AST, ast.AST]) -> bool:
    """Whether ``type(...)`` asks nothing about an object: ``type(None)``, an
    argument of ``isinstance``/``issubclass`` (that call is judged), or the
    class ``type(x)(...)`` builds an object of."""
    if _none_type(call):
        return True
    parent = parents.get(call)
    if not isinstance(parent, ast.Call):
        return False
    if parent.func is call:
        return True
    return (
        isinstance(parent.func, ast.Name)
        and parent.func.id in _CLASS_TAKING
        and call in parent.args
    )


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
    parent: Optional[ast.AST] = parents.get(node)
    named = False
    if isinstance(parent, ast.Attribute) and parent.attr in _NAME_ATTRIBUTES:
        node, parent, named = parent, parents.get(parent), True
    shown = False
    while True:
        if isinstance(parent, ast.Tuple):
            outer = parents.get(parent)
            if outer is not None and _formatted(outer, parent):
                node, parent = parent, outer  # "%s %s" % (a, type(x))
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
        elif _logged(parent, node):
            return True  # a logging call returns nothing to decide by
        elif (
            isinstance(parent, ast.Call)
            and isinstance(parent.func, ast.Attribute)
            and parent.func.attr == "format"
            and (node in parent.args or any(k.value is node for k in parent.keywords))
        ):
            node = parent  # "{}".format(type(x))
        elif parent is not None and _formatted(parent, node):
            node = parent  # "%s" % type(x)
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


def _formatted(parent: Optional[ast.AST], node: ast.AST) -> bool:
    """Whether ``node`` is the right side of a ``%`` whose left side is a
    string (a format, not a remainder)."""
    return (
        isinstance(parent, ast.BinOp)
        and isinstance(parent.op, ast.Mod)
        and parent.right is node
        and isinstance(parent.left, (ast.Constant, ast.JoinedStr))
        and (
            not isinstance(parent.left, ast.Constant)
            or isinstance(parent.left.value, str)
        )
    )


def _logged(parent: Optional[ast.AST], node: ast.AST) -> bool:
    """Whether ``node`` is an argument of a logging call (``log.warning(...)``,
    ``logging.error(...)``, ``self.logger.info(...)``)."""
    return (
        isinstance(parent, ast.Call)
        and isinstance(parent.func, ast.Attribute)
        and parent.func.attr in _LOGGING
        and ast_utils.dotted(parent.func.value) is not None
        and node in parent.args
    )


__all__ = ["TYPE_TEST_CALLEES", "TypeTests"]
