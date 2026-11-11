"""Small judgements about code read from its AST, shared by the static
checks, the mutation operators and global mode.

Each judgement has one copy here, so the copies cannot drift apart. Where
callers deliberately apply different rules (how strictly a decorator or a
base must be spelled, whether a ``pass`` body declares a method abstract),
each rule is a separate function whose docstring says how it differs from
the others; the shared mechanics (a docstring, a stub statement) are common.

Abstract methods, from the strictest rule to the loosest:

- ``never_runs`` (mutation): an exact abstract decorator, or a body (past a
  docstring) of stub statements only, none at all included;
- ``is_abstract_method`` (global mode): a decorator whose text contains
  ``abstractmethod``, or a body (past a docstring) of exactly one stub
  statement;
- ``declares_abstract`` (global mode's polymorphism): ``is_abstract_method``
  without the one-statement ``pass`` body, which is a default that does
  nothing rather than a declaration.

Abstract classes: ``is_abstract_class`` (mutation) matches the exact
spellings of ``ABSTRACT_BASES``, ``ABSTRACT_METACLASSES`` and
``ABSTRACT_DECORATORS``; ``is_interface`` (principles, global mode) matches a
base by its last name, a metaclass and a decorator by a substring.
"""

from __future__ import annotations

import ast
from typing import Iterator, Optional

# --- statements -----------------------------------------------------------


def is_docstring(node: ast.stmt) -> bool:
    """Whether the statement is a string constant on its own (a docstring
    when it comes first)."""
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def body_past_docstring(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.stmt]:
    """The function's body without a leading docstring."""
    body = list(function.body)
    return body[1:] if body and is_docstring(body[0]) else body


def is_ellipsis_statement(statement: ast.stmt) -> bool:
    """``...`` on its own."""
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and statement.value.value is Ellipsis
    )


def raises_not_implemented(statement: ast.stmt) -> bool:
    """``raise NotImplementedError`` or ``raise NotImplementedError(...)``."""
    if not isinstance(statement, ast.Raise) or statement.exc is None:
        return False
    raised = statement.exc
    if isinstance(raised, ast.Call):
        raised = raised.func
    return isinstance(raised, ast.Name) and raised.id == "NotImplementedError"


def is_stub_statement(statement: ast.stmt) -> bool:
    """``pass``, ``...`` or ``raise NotImplementedError`` (called or not)."""
    return (
        isinstance(statement, ast.Pass)
        or is_ellipsis_statement(statement)
        or raises_not_implemented(statement)
    )


# --- abstract methods -----------------------------------------------------

# The decorators that make a method abstract, as ``ast.unparse`` spells them
# (``ABSTRACT_BASES`` has the bases).
ABSTRACT_DECORATORS = frozenset(
    prefix + name
    for prefix in ("", "abc.")
    for name in (
        "abstractmethod",
        "abstractproperty",
        "abstractclassmethod",
        "abstractstaticmethod",
    )
)


def has_abstract_decorator(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether a decorator is spelled exactly as one of ``ABSTRACT_DECORATORS``."""
    return any(ast.unparse(d) in ABSTRACT_DECORATORS for d in function.decorator_list)


def mentions_abstractmethod(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether a decorator's text contains ``abstractmethod`` (``abc.abstractmethod``,
    ``abstractmethod``, any other spelling that contains it); unlike
    ``has_abstract_decorator``, ``abstractproperty`` does not count."""
    return any("abstractmethod" in ast.unparse(d) for d in function.decorator_list)


def never_runs(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether ``function``'s code never runs as a case calls it: an abstract
    method (``has_abstract_decorator``), or a stub whose body is only a
    docstring, ``...``, ``pass`` or ``raise NotImplementedError``, any number
    of them. A mutant there could not be killed."""
    if has_abstract_decorator(function):
        return True
    return all(is_stub_statement(s) for s in body_past_docstring(function))


def only_raises_not_implemented(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether the body, past a docstring, is one ``raise NotImplementedError``."""
    body = body_past_docstring(node)
    return len(body) == 1 and raises_not_implemented(body[0])


def is_abstract_method(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether the method is abstract: decorated with ``abstractmethod``
    (``mentions_abstractmethod``), or its body (past a docstring) is one
    statement that only raises ``NotImplementedError`` or is ``...`` or
    ``pass``. No case can run such a method on an object of its own class.
    Unlike ``never_runs``, a body of only a docstring, or of several stub
    statements, is not abstract."""
    if mentions_abstractmethod(node):
        return True
    body = body_past_docstring(node)
    return len(body) == 1 and is_stub_statement(body[0])


def declares_abstract(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """``is_abstract_method`` but for an undecorated ``pass`` body: such a
    method is a default that does nothing, not a declaration."""
    if mentions_abstractmethod(node):
        return True
    return is_abstract_method(node) and not isinstance(node.body[-1], ast.Pass)


# --- abstract classes -----------------------------------------------------

# What makes a class abstract by its own code: a base, a metaclass, a
# decorator of a method (``ABSTRACT_DECORATORS``), as ``ast.unparse`` spells
# them; a generic ``Protocol[T]`` by its value.
ABSTRACT_BASES = frozenset(
    {"ABC", "abc.ABC", "Protocol", "typing.Protocol", "typing_extensions.Protocol"}
)


ABSTRACT_METACLASSES = frozenset({"ABCMeta", "abc.ABCMeta"})


def abstract_base(base: ast.expr) -> bool:
    """Whether a base (its value, for ``Protocol[T]``) is spelled exactly as
    one of ``ABSTRACT_BASES``."""
    node = base.value if isinstance(base, ast.Subscript) else base
    return ast.unparse(node) in ABSTRACT_BASES


def is_abstract_class(cls: ast.ClassDef) -> bool:
    """Whether ``cls`` is abstract by its own code (a base, a metaclass, an
    abstract method), each spelled exactly as ``ABSTRACT_BASES``,
    ``ABSTRACT_METACLASSES`` and ``ABSTRACT_DECORATORS`` list it: such a
    class cannot be built."""
    return (
        any(abstract_base(base) for base in cls.bases)
        or any(
            k.arg == "metaclass" and ast.unparse(k.value) in ABSTRACT_METACLASSES
            for k in cls.keywords
        )
        or any(
            has_abstract_decorator(item)
            for item in cls.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        )
    )


def base_names(node: ast.ClassDef) -> set[str]:
    """The last part of each base a class statement names (``Protocol`` for
    ``typing.Protocol[T]``)."""
    names = set()
    for base in node.bases:
        if isinstance(base, ast.Subscript):
            base = base.value  # Protocol[T]
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


_INTERFACE_BASES = frozenset({"ABC", "Protocol"})


def is_interface(node: ast.ClassDef) -> bool:
    """Whether the class is an interface: ``ABC`` or ``Protocol`` among its
    bases, ``metaclass=ABCMeta``, or an ``@abstractmethod``. Looser than
    ``is_abstract_class``: a base counts by its last name (``base_names``),
    a metaclass whose text contains ``ABCMeta`` and a method decorator whose
    text contains ``abstractmethod`` (``mentions_abstractmethod``) count."""
    if base_names(node) & _INTERFACE_BASES or any(
        k.arg == "metaclass" and "ABCMeta" in ast.unparse(k.value)
        for k in node.keywords
    ):
        return True
    return any(
        mentions_abstractmethod(item)
        for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


# --- functions ------------------------------------------------------------


def self_parameter(function: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[str]:
    """The name of the function's first positional parameter (a method's
    ``self``), else ``None``."""
    args = function.args.posonlyargs + function.args.args
    return args[0].arg if args else None


def kept_names(
    method: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Iterator[tuple[ast.stmt, str, ast.Name]]:
    """Each ``self.x = name`` (also ``self.x: T = name``) in ``method``, in
    ``ast.walk`` order: the statement, the attribute and the name assigned;
    ``self`` is the method's first parameter (``self_parameter``)."""
    self_name = self_parameter(method)
    for node in ast.walk(method):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target: ast.expr = node.targets[0]
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target = node.target
        else:
            continue
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == self_name
            and isinstance(node.value, ast.Name)
        ):
            yield node, target.attr, node.value


# --- names ----------------------------------------------------------------


def is_private(attribute: str) -> bool:
    """An attribute starting with ``_`` that is no dunder (``__x`` and the
    mangled ``_Owner__x`` are private)."""
    return attribute.startswith("_") and not (
        attribute.startswith("__") and attribute.endswith("__")
    )


def annotated_class(annotation: Optional[ast.expr]) -> Optional[str]:
    """The class name a parameter's annotation names (``Inventory``,
    ``inventory.Inventory``, ``"Inventory"``), else ``None``."""
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        name = annotation.value.rpartition(".")[2]
        return name if name.isidentifier() else None
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Attribute):
        return annotation.attr
    return None


def dotted(node: ast.expr) -> Optional[str]:
    """``a.b.c`` of a chain of attributes on a name (``a`` of a name), else
    ``None``. Unlike ``protocols.type_expr.dotted_name``, which gives the
    attributes alone (``x`` of ``f().x``) when the chain does not start at
    a name, any other start gives ``None``."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


__all__ = [
    "ABSTRACT_BASES",
    "ABSTRACT_DECORATORS",
    "ABSTRACT_METACLASSES",
    "abstract_base",
    "annotated_class",
    "base_names",
    "body_past_docstring",
    "declares_abstract",
    "dotted",
    "has_abstract_decorator",
    "is_abstract_class",
    "is_abstract_method",
    "is_docstring",
    "is_ellipsis_statement",
    "is_interface",
    "is_private",
    "is_stub_statement",
    "kept_names",
    "mentions_abstractmethod",
    "never_runs",
    "only_raises_not_implemented",
    "raises_not_implemented",
    "self_parameter",
]
