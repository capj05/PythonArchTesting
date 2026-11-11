"""Evaluator for ``forbid_private_access``: no private attribute read from outside.

A static check of the matched target function or method. Every ``obj._x``
its body reads (``_x`` starts with an underscore and is no dunder), and every
read of a constant private name through ``getattr(obj, "_x")``,
``vars(obj)["_x"]`` or ``obj.__dict__["_x"]``, is a violation, unless

- ``obj`` is the method's own instance or class: its first parameter
  (``self``, ``cls``, whatever it is called; not in a static method),
  ``super()``, ``type(self)`` or ``self.__class__``;
- the method belongs to the class that defines ``_x`` or to a subclass of a
  project class that does (a class-level name, a method, or what its methods
  assign to their ``self``, in a tuple too): another instance of the same
  class (``other._x`` in ``__eq__``) is the class's own business;
- ``obj`` is a name an import binds to a module (``module._helper``) and the
  function binds no name of its own so (a parameter, a local): a module's
  private names are ``module_interface``'s concern, not an object's;
- ``_x`` is public by convention: the API of a named tuple (``_replace``,
  ``_asdict``, ``_fields``, ``_make``, ``_field_defaults``) or a sunder name
  such as an enum member's ``_value_`` and ``_name_``;
- ``_x`` is listed in ``allow``.

Only reads count. Assigning or deleting the attribute, or an item of it
(``obj._x = v``, ``obj._x[k] = v``, ``del obj._x[k]``), is a write, which
``forbid_foreign_writes`` reports with what changed. Code outside the
function (default values, decorators, the module's top level, which runs at
import time) and classes defined inside it are not checked.

Each violation has a fact in ``details.facts`` (aligned 1:1 with
``details.violations``): ``kind`` ``read``, ``attribute``, ``class`` (named
by the annotation of the parameter read through, else ``None``), ``file``,
``line`` and ``reader`` (``module:qualname``).
"""

from __future__ import annotations

import ast
from typing import Any, Iterator, NamedTuple, Optional

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.entities import Entity
from pythonarchtesting.execution.import_edges import _resolve_relative_module
from pythonarchtesting.matching import MatchResult
from pythonarchtesting.protocols.entity_lookup import ProtocolEntityLookup

from .messages import MAX_REPORTED, _build_rule_result, finish_violations

_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


# Names starting with "_" that are a named tuple's public API.
NAMED_TUPLE_API = frozenset(
    {"_replace", "_asdict", "_fields", "_make", "_field_defaults"}
)


def is_private(attribute: str) -> bool:
    """An attribute starting with ``_`` that is no dunder (``__x`` and the
    mangled ``_Owner__x`` are private)."""
    return attribute.startswith("_") and not (
        attribute.startswith("__") and attribute.endswith("__")
    )


def _public_by_convention(attribute: str) -> bool:
    """A named tuple's API, or a sunder name (``_value_``, ``_name_``)."""
    sunder = (
        len(attribute) > 2
        and attribute[0] == attribute[-1] == "_"
        and attribute[1] != "_"
        and attribute[-2] != "_"
    )
    return sunder or attribute in NAMED_TUPLE_API


class PrivateRead(NamedTuple):
    """One read of a private attribute: the node it is read at, the object
    expression read from and the attribute's name."""

    node: ast.expr
    value: ast.expr
    attr: str
    # The object a method is called on (``obj._x.append(v)``): the read may
    # be only the way a write changes ``_x``.
    receiver: bool = False
    # The change that write makes: ``mutated`` (a method changes the
    # contents) or ``assigned`` (the statement rebuilds the attribute).
    change: str = ""


def _first_parameter(function: ast.AST) -> Optional[str]:
    """The name a method's first parameter binds (its instance or class)."""
    if not isinstance(function, _FUNCTIONS):
        return None
    for decorator in function.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "staticmethod":
            return None
    arguments = function.args.posonlyargs + function.args.args
    return arguments[0].arg if arguments else None


def _annotated_class(annotation: Optional[ast.expr]) -> Optional[str]:
    """The class a parameter's annotation names: ``Inventory``,
    ``inventory.Inventory`` or ``"Inventory"``; ``None`` for anything else."""
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        name = annotation.value.rpartition(".")[2]
        return name if name.isidentifier() else None
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Attribute):
        return annotation.attr
    return None


def _own(value: ast.expr, self_name: Optional[str]) -> bool:
    """Whether ``value`` is the method's own instance or class."""
    if self_name is None:
        return False
    if isinstance(value, ast.Name):
        return value.id == self_name
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        if value.func.id == "super":
            return True
        return (
            value.func.id == "type"
            and len(value.args) == 1
            and isinstance(value.args[0], ast.Name)
            and value.args[0].id == self_name
        )
    return (
        isinstance(value, ast.Attribute)
        and value.attr == "__class__"
        and isinstance(value.value, ast.Name)
        and value.value.id == self_name
    )


def self_assigned(function: ast.AST, self_name: Optional[str]) -> list[str]:
    """The attributes ``function`` assigns to ``self_name``, in source order:
    ``self.x = v``, ``self.x += v``, ``self.x: T = v`` and every target of an
    unpacking (``self.x, self.y = v``, ``[self.x, *self.rest] = v``) or of a
    ``for``/``with``."""
    if self_name is None:
        return []
    found = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Store)
        and isinstance(node.value, ast.Name)
        and node.value.id == self_name
    ]
    found.sort(key=lambda n: (n.lineno, n.col_offset))
    return [node.attr for node in found]


def _defined(cls: ast.ClassDef) -> set[str]:
    """What a class defines: class-level names, its methods, what its methods
    assign to their first parameter, each also name-mangled (``_C__x``)."""
    names: set[str] = set()
    for node in cls.body:
        if isinstance(node, _FUNCTIONS):
            names.add(node.name)
            names.update(self_assigned(node, _first_parameter(node)))
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    mangled = {
        f"_{cls.name.lstrip('_')}{name}"
        for name in names
        if name.startswith("__") and not name.endswith("__")
    }
    return names | mangled


def _owning_class(target: Entity, ctx: EvalContext) -> Optional[Entity]:
    """The class a method target belongs to."""
    if target.kind != "method":
        return None
    owner = str(target.qualname).rpartition(".")[0]
    for entity in _entities(ctx):
        if (
            entity.kind == "class"
            and entity.module_path == target.module_path
            and entity.qualname == owner
        ):
            return entity
    return None


def _class_defined(cls: Optional[Entity], ctx: EvalContext) -> set[str]:
    """What a class and the project classes it derives from define."""
    if cls is None:
        return set()
    lookup = ProtocolEntityLookup.from_entities(_entities(ctx))
    names: set[str] = set()
    seen: set[str] = set()
    pending = [cls]
    while pending:
        entity = pending.pop()
        if entity.canonical_id in seen:
            continue
        seen.add(entity.canonical_id)
        node = entity.extras.get("ast_node")
        if isinstance(node, ast.ClassDef):
            names |= _defined(node)
        pending.extend(lookup.resolved_bases(entity))
    return names


def _entities(ctx: EvalContext) -> list[Entity]:
    index = getattr(ctx, "target_index", None)
    return list(getattr(index, "all_sorted", None) or ctx.target_by_id.values())


def _own_name(name: str, package: Optional[str]) -> str:
    """An absolute module name without the project's package prefix."""
    if package and name == package:
        return ""
    if package and name.startswith(f"{package}."):
        return name[len(package) + 1 :]
    return name


def _module_names(target: Entity, ctx: EvalContext) -> set[str]:
    """The names the target's module binds to a module by an import:
    ``import x`` (``x``), ``import x as y``, and ``from p import m`` when
    ``p.m`` is a module of the project."""
    entities = _entities(ctx)
    modules = {str(e.module_path) for e in entities if e.kind == "module"}
    tree = next(
        (
            e.extras.get("ast_node")
            for e in entities
            if e.kind == "module" and e.module_path == target.module_path
        ),
        None,
    )
    if tree is None:
        return set()
    package = getattr(ctx, "target_package", None)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(
                alias.asname or alias.name.split(".")[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            base = (
                _resolve_relative_module(
                    importer_module=str(target.module_path),
                    filepath_rel=str(target.filepath_rel),
                    level=node.level,
                    module=node.module,
                )
                if node.level
                else _own_name(node.module or "", package)
            )
            for alias in node.names:
                full = f"{base}.{alias.name}" if base else alias.name
                if full in modules:
                    names.add(alias.asname or alias.name)
    return names


def _local_names(function: ast.AST) -> set[str]:
    """The names ``function`` binds itself (parameters, locals, local
    functions, classes and imports, also in nested functions): none of them
    is a module the module imports."""
    names: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif node is not function and isinstance(node, (*_FUNCTIONS, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(
                alias.asname or alias.name.split(".")[0] for alias in node.names
            )
    return names


def _written(body: list[ast.stmt]) -> set[int]:
    """``id`` of each ``obj._x`` that is the object of an item write
    (``obj._x[k] = v``, ``obj._x[k] += v``, ``del obj._x[k]``)."""
    return {
        id(node.value)
        for statement in body
        for node in ast.walk(statement)
        if isinstance(node, ast.Subscript)
        and isinstance(node.ctx, (ast.Store, ast.Del))
        and isinstance(node.value, ast.Attribute)
    }


def _rebuilt(body: list[ast.stmt]) -> set[int]:
    """``id`` of each ``obj._x`` read in a statement that assigns ``obj._x``
    itself (``obj._x = {k: v for k, v in obj._x.items() if ...}``): the
    attribute is read to rebuild it, which is part of that write. A read of
    another object (``a._x = b._x.copy()``) is not."""
    found: set[int] = set()
    for node in _walk(body):
        if not isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        assigned = {
            (ast.unparse(target.value), target.attr)
            for target in targets
            if isinstance(target, ast.Attribute)
        }
        if not assigned or node.value is None:
            continue
        found.update(
            id(read)
            for read in ast.walk(node.value)
            if isinstance(read, ast.Attribute)
            and isinstance(read.ctx, ast.Load)
            and (ast.unparse(read.value), read.attr) in assigned
        )
    return found


def _walk(body: list[ast.stmt]) -> Iterator[ast.AST]:
    """Every node of ``body``, nested functions and lambdas included, but not
    the classes defined in it (their methods have their own ``self``)."""
    stack: list[ast.AST] = list(reversed(body))
    while stack:
        node = stack.pop()
        if isinstance(node, ast.ClassDef):
            continue
        yield node
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def _constant_name(node: ast.expr) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _read(node: ast.AST) -> Optional[PrivateRead]:
    """The attribute ``node`` reads, if it reads one: ``obj.x``,
    ``getattr(obj, "x")``, ``vars(obj)["x"]`` or ``obj.__dict__["x"]``."""
    if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
        return PrivateRead(node, node.value, node.attr)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
    ):
        name = _constant_name(node.args[1])
        return PrivateRead(node, node.args[0], name) if name else None
    if not (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load)):
        return None
    name = _constant_name(node.slice)
    holder = node.value
    if name is None:
        return None
    if (
        isinstance(holder, ast.Call)
        and isinstance(holder.func, ast.Name)
        and holder.func.id == "vars"
        and len(holder.args) == 1
    ):
        return PrivateRead(node, holder.args[0], name)
    if isinstance(holder, ast.Attribute) and holder.attr == "__dict__":
        return PrivateRead(node, holder.value, name)
    return None


# The methods that change a container in place: a private attribute read only
# to call one of them (``obj._x.append(v)``) is part of that write.
MUTATING_METHODS = frozenset(
    {
        "append",
        "extend",
        "insert",
        "update",
        "pop",
        "popitem",
        "remove",
        "clear",
        "setdefault",
        "add",
        "discard",
        "sort",
        "reverse",
        "appendleft",
        "extendleft",
        "popleft",
        "difference_update",
        "intersection_update",
        "symmetric_difference_update",
    }
)


def private_reads(
    function: ast.AST,
    *,
    self_name: Optional[str],
    defined: set[str],
    modules: set[str],
    allow: set[str],
) -> list[PrivateRead]:
    """The private attributes ``function``'s body reads from outside, in
    source order (an inner read of a chain first)."""
    body = list(getattr(function, "body", []) or [])
    written = _written(body)
    changed = {
        id(node.func.value)
        for node in _walk(body)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in MUTATING_METHODS
    }
    rebuilt = _rebuilt(body)
    modules = modules - _local_names(function)
    found = [
        read._replace(
            receiver=id(read.node) in changed or id(read.node) in rebuilt,
            change=(
                "mutated"
                if id(read.node) in changed
                else "assigned" if id(read.node) in rebuilt else ""
            ),
        )
        for read in map(_read, _walk(body))
        if read is not None
        and is_private(read.attr)
        and not _public_by_convention(read.attr)
        and read.attr not in allow
        and read.attr not in defined
        and id(read.node) not in written
        and not _own(read.value, self_name)
        and not (isinstance(read.value, ast.Name) and read.value.id in modules)
    ]
    return sorted(
        found,
        key=lambda r: (r.node.lineno, r.node.col_offset, r.node.end_col_offset or 0),
    )


def _parameter_classes(function: ast.AST) -> dict[str, Optional[str]]:
    if not isinstance(function, _FUNCTIONS):
        return {}
    arguments = function.args
    return {
        a.arg: _annotated_class(a.annotation)
        for a in arguments.posonlyargs + arguments.args + arguments.kwonlyargs
    }


class PrivateAccessEvaluator:
    """Static ``forbid_private_access`` on one matched function or method."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        function = target.extras.get("ast_node")
        reader = f"{target.module_path}:{target.qualname}"
        details: dict[str, Any] = {"reason": "", "summary": "", "reader": reader}
        if not isinstance(function, _FUNCTIONS):
            details["reason"] = "missing_function_body"
            details["summary"] = f"{reader} has no function body to check"
            return _build_rule_result(rule, source, target, match, "ERROR", details, ())
        self_name = _first_parameter(function) if target.kind == "method" else None
        reads = private_reads(
            function,
            self_name=self_name,
            defined=_class_defined(_owning_class(target, ctx), ctx),
            modules=_module_names(target, ctx),
            allow={str(name) for name in rule.params.get("allow") or []},
        )
        classes = _parameter_classes(function)
        file = str(target.filepath_rel)
        violations: list[str] = []
        facts: list[dict[str, Any]] = []
        for read in reads:
            obj = ast.unparse(read.value)
            owner = (
                classes.get(read.value.id) if isinstance(read.value, ast.Name) else None
            )
            line = read.node.lineno
            facts.append(
                {
                    "kind": "read",
                    "attribute": read.attr,
                    "class": owner,
                    "file": file,
                    "line": line,
                    "reader": reader,
                    **({"receiver": read.change} if read.receiver else {}),
                }
            )
            of = f"{obj} ({owner})" if owner else obj
            violations.append(
                f"{reader} reads private attribute {read.attr} of {of} at "
                f"{file}:{line}"
            )
        if facts:
            details["facts"] = facts[:MAX_REPORTED]
        return finish_violations(
            rule,
            source,
            target,
            match,
            details,
            violations,
            f"{reader} reads no private attribute of another object",
        )


__all__ = [
    "NAMED_TUPLE_API",
    "PrivateAccessEvaluator",
    "PrivateRead",
    "is_private",
    "private_reads",
    "self_assigned",
]
