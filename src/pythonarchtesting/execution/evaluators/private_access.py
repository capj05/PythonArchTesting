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
  assign to their ``self``, in a tuple too), and ``obj`` is another instance
  of the same class: another instance (``other._x`` in ``__eq__``) is the
  class's own business. ``obj`` is known to be one when it is annotated with
  the class or one of its project bases (``other: "Cart"``), is built by it
  (``Cart()``, ``cls()``, ``type(self)()``, a local assigned so), is the
  class itself (``Cart._made``), is proved one by an ``isinstance`` check
  (``isinstance(other, Cart) and other._x``, ``if not isinstance(...):
  return``) or is the unannotated ``other`` of a comparison or binary
  dunder (``__eq__``, ``__add__``); a class named through an import is told
  by the module it comes from (``views.Item`` is not ``models.Item``), one
  no import or class statement binds by its simple name. Any other ``obj``
  counts as one only when no
  project class outside the class's family (its bases and subclasses)
  defines ``_x`` too, so ``inv._items`` in ``Cart.checkout`` is foreign when
  ``Inventory`` has an ``_items`` as well;
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
import weakref
from typing import Any, Iterator, NamedTuple, Optional

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.entities import Entity
from pythonarchtesting.execution.import_edges import resolve_relative_module
from pythonarchtesting.matching import MatchResult
from pythonarchtesting.protocols.entity_lookup import ProtocolEntityLookup
from pythonarchtesting.util.ast_utils import annotated_class, is_private
from pythonarchtesting.util.module_names import strip_package

from .messages import MAX_REPORTED, build_rule_result, finish_violations

_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


# Names starting with "_" that are a named tuple's public API.
NAMED_TUPLE_API = frozenset(
    {"_replace", "_asdict", "_fields", "_make", "_field_defaults"}
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


class _Scope(NamedTuple):
    """What the names of a module are bound to by its imports and its class
    statements: a module (``models``) or a class (``models:Item``)."""

    modules: dict[str, str]
    classes: dict[str, str]

    def resolve(self, node: ast.expr) -> Optional[str]:
        """``module:qualname`` of the class ``node`` names (``Item``,
        ``views.Item``, ``Outer.Inner``); ``None`` when the module binds no
        name it starts with."""
        if isinstance(node, ast.Name):
            return self.classes.get(node.id)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            base = node.value.id
            if base in self.classes:
                return f"{self.classes[base]}.{node.attr}"
            if base in self.modules:
                return f"{self.modules[base]}:{node.attr}"
        return None


class KnownClasses(NamedTuple):
    """The classes of a method's family: their simple names and, to tell
    ``views.Item`` from ``models.Item``, their ``module:qualname`` with the
    scope of the module that names them."""

    simple: frozenset[str] = frozenset()
    qualified: frozenset[str] = frozenset()
    scope: Optional[_Scope] = None

    def named(self, node: Optional[ast.expr]) -> bool:
        """Whether ``node`` (also a string annotation) names one of the
        classes: by the class an import or class statement binds the name
        to, else, when nothing binds it, by its simple name."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                node = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                return False
        if node is None:
            return False
        resolved = self.scope.resolve(node) if self.scope is not None else None
        if resolved is not None:
            return resolved in self.qualified
        return _class_name(node) in self.simple


class _Family(NamedTuple):
    """What a method's class knows of itself: what it and its project bases
    define, which classes they are, and what the project classes outside its
    family (neither a base nor a subclass) define."""

    defined: set[str]
    names: KnownClasses
    foreign: set[str]


def _ancestors(cls: Entity, lookup: ProtocolEntityLookup) -> list[Entity]:
    """``cls`` and the project classes it derives from."""
    found: list[Entity] = []
    seen: set[str] = set()
    pending = [cls]
    while pending:
        entity = pending.pop()
        if entity.canonical_id in seen:
            continue
        seen.add(entity.canonical_id)
        found.append(entity)
        pending.extend(lookup.resolved_bases(entity))
    return found


# The lookup of the last evaluation context: ``(context, its entities, lookup)``.
# A target's rules share it; it is built again for another context, or when
# the context's entities are no longer the same objects.
_LAST_LOOKUP: Optional[
    tuple[weakref.ReferenceType[Any], list[Entity], ProtocolEntityLookup]
] = None


def _lookup(ctx: EvalContext, entities: list[Entity]) -> ProtocolEntityLookup:
    """The project's ``ProtocolEntityLookup``, built once per evaluation context."""
    global _LAST_LOOKUP  # pylint: disable=global-statement
    last = _LAST_LOOKUP
    if (
        last is not None
        and last[0]() is ctx
        and len(last[1]) == len(entities)
        and all(kept is entity for kept, entity in zip(last[1], entities))
    ):
        return last[2]
    lookup = ProtocolEntityLookup.from_entities(entities)
    try:
        _LAST_LOOKUP = (weakref.ref(ctx), entities, lookup)
    except TypeError:  # a context that cannot be referenced weakly
        _LAST_LOOKUP = None
    return lookup


def _class_family(
    cls: Optional[Entity], ctx: EvalContext, scope: Optional[_Scope] = None
) -> _Family:
    """What a class and the project classes it derives from define, which
    classes they are (named in ``scope``), and what every other project class
    not derived from it defines."""
    if cls is None:
        return _Family(set(), KnownClasses(), set())
    entities = _entities(ctx)
    lookup = _lookup(ctx, entities)
    family = _ancestors(cls, lookup)
    defined: set[str] = set()
    for entity in family:
        node = entity.extras.get("ast_node")
        if isinstance(node, ast.ClassDef):
            defined |= _defined(node)
    names = KnownClasses(
        frozenset(str(e.qualname).rpartition(".")[2] for e in family),
        frozenset(f"{e.module_path}:{e.qualname}" for e in family),
        scope,
    )
    foreign: set[str] = set()
    for entity in entities:
        node = entity.extras.get("ast_node")
        if entity.kind != "class" or not isinstance(node, ast.ClassDef):
            continue
        if any(e.canonical_id == cls.canonical_id for e in _ancestors(entity, lookup)):
            continue  # the class itself or a subclass of it
        if any(e.canonical_id == entity.canonical_id for e in family):
            continue  # one of its bases
        foreign |= _defined(node)
    return _Family(defined, names, foreign)


def _entities(ctx: EvalContext) -> list[Entity]:
    index = getattr(ctx, "target_index", None)
    return list(getattr(index, "all_sorted", None) or ctx.target_by_id.values())


def _own_name(name: str, package: Optional[str]) -> str:
    """An absolute module name without the project's package prefix."""
    stripped = strip_package(name, package)
    return name if stripped is None else stripped


def _import_scope(target: Entity, ctx: EvalContext) -> _Scope:
    """What the target's module binds by an import or a class statement.

    To a module: ``import x`` (``x``), ``import x as y``, and
    ``from p import m`` when ``p.m`` is a module of the project. To a class
    (or any other name): ``from p import C`` (``p:C``) and the module's own
    top-level classes."""
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
    scope = _Scope({}, {})
    if tree is None:
        return scope
    package = getattr(ctx, "target_package", None)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.name if alias.asname else alias.name.split(".")[0]
                scope.modules[alias.asname or bound] = _own_name(bound, package)
        elif isinstance(node, ast.ImportFrom):
            base = (
                resolve_relative_module(
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
                    scope.modules[alias.asname or alias.name] = full
                else:
                    scope.classes[alias.asname or alias.name] = f"{base}:{alias.name}"
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.ClassDef):
            scope.classes[node.name] = f"{target.module_path}:{node.name}"
    return scope


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


def _class_name(node: ast.expr) -> Optional[str]:
    """The name of the class ``node`` names: ``Cart`` or ``model.Cart``."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _same_class(
    value: ast.expr,
    *,
    self_name: Optional[str],
    classes: KnownClasses,
    instances: set[str],
) -> bool:
    """Whether ``value`` is known to be the class itself or an instance of
    it: one of ``classes`` (``Cart._made``), a name in ``instances`` or what
    the class builds (``Cart()``, ``cls()``, ``type(self)()``,
    ``self.__class__()``)."""
    if isinstance(value, ast.Name):
        return value.id in instances or classes.named(value)
    if not isinstance(value, ast.Call):
        return False
    return classes.named(value.func) or _own(value.func, self_name)


# The dunders of a binary operator or a comparison: their ``other`` is
# taken to be another instance of the class unless annotated otherwise.
BINARY_DUNDERS = frozenset(
    {f"__{name}__" for name in ("eq", "ne", "lt", "le", "gt", "ge")}
    | {
        f"__{prefix}{name}__"
        for prefix in ("", "r", "i")
        for name in (
            "add",
            "sub",
            "mul",
            "matmul",
            "truediv",
            "floordiv",
            "mod",
            "divmod",
            "pow",
            "lshift",
            "rshift",
            "and",
            "xor",
            "or",
        )
    }
)


def _instances(
    function: ast.AST, self_name: Optional[str], classes: KnownClasses
) -> set[str]:
    """The names ``function`` binds to an instance of one of ``classes``:
    parameters and locals annotated with one (``other: "Cart"``), the
    unannotated ``other`` of a binary or comparison dunder (``__eq__``), and
    locals every assignment of which builds one (``fresh = type(self)()``)."""
    if not classes.simple:
        return set()
    annotations = _parameter_annotations(function)
    found = {
        name for name, annotation in annotations.items() if classes.named(annotation)
    }
    if self_name is not None and getattr(function, "name", "") in BINARY_DUNDERS:
        other = list(annotations)[1:2]
        found.update(name for name in other if annotations[name] is None)
    built: dict[str, bool] = {}
    for node in _walk(list(getattr(function, "body", []) or [])):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if classes.named(node.annotation):
                found.add(node.target.id)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    made = isinstance(node.value, ast.Call) and _same_class(
                        node.value,
                        self_name=self_name,
                        classes=classes,
                        instances=set(),
                    )
                    built[target.id] = built.get(target.id, True) and made
    return found | {name for name, made in built.items() if made}


def _checked(test: ast.expr, classes: KnownClasses) -> set[str]:
    """The names ``test`` being true proves instances of ``classes``:
    ``isinstance(name, Cart)`` (or a tuple holding ``Cart``), also as one
    operand of an ``and``."""
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        return set().union(*(_checked(value, classes) for value in test.values))
    if not (
        isinstance(test, ast.Call)
        and isinstance(test.func, ast.Name)
        and test.func.id == "isinstance"
        and len(test.args) == 2
        and isinstance(test.args[0], ast.Name)
    ):
        return set()
    kinds = test.args[1]
    options = kinds.elts if isinstance(kinds, ast.Tuple) else [kinds]
    return {test.args[0].id} if any(map(classes.named, options)) else set()


def _refuted(test: ast.expr, classes: KnownClasses) -> set[str]:
    """The names ``test`` being false proves instances of ``classes``:
    ``not isinstance(name, Cart)``, also as one operand of an ``or``."""
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
        return set().union(*(_refuted(value, classes) for value in test.values))
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return _checked(test.operand, classes)
    return set()


def _narrowed(body: list[ast.stmt], classes: KnownClasses) -> set[tuple[str, int]]:
    """``(name, id)`` of each name node ``isinstance`` proves an instance of
    ``classes``: in the body of ``if isinstance(name, Cart)``, the later
    operands of ``isinstance(name, Cart) and ...``, the branch of a
    conditional expression, and the statements after ``assert
    isinstance(...)`` or ``if not isinstance(...): return`` (or ``raise``,
    ``continue``, ``break``) in the same block."""
    found: set[tuple[str, int]] = set()

    def mark(names: set[str], nodes: list[Any]) -> None:
        found.update(
            (node.id, id(node))
            for top in nodes
            for node in ast.walk(top)
            if isinstance(node, ast.Name) and node.id in names
        )

    blocks = [body]
    for node in _walk(body):
        if isinstance(node, (ast.If, ast.IfExp)):
            mark(_checked(node.test, classes), _as_list(node.body))
            mark(_refuted(node.test, classes), _as_list(node.orelse))
        elif isinstance(node, ast.BoolOp):
            prove = _checked if isinstance(node.op, ast.And) else _refuted
            for index, value in enumerate(node.values):
                mark(prove(value, classes), node.values[index + 1 :])
        blocks.extend(_blocks(node))
    for block in blocks:
        for index, statement in enumerate(block):
            mark(_guarded(statement, classes), block[index + 1 :])
    return found


def _as_list(part: Any) -> list[Any]:
    return part if isinstance(part, list) else [part]


def _blocks(node: ast.AST) -> Iterator[list[ast.stmt]]:
    for field in ("body", "orelse", "finalbody"):
        block = getattr(node, field, None)
        if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
            yield block


def _guarded(statement: ast.stmt, classes: KnownClasses) -> set[str]:
    """The names the statements after ``statement`` know to be instances of
    ``classes``: ``assert isinstance(...)``, or an ``if not isinstance(...)``
    whose body always leaves the block."""
    if isinstance(statement, ast.Assert):
        return _checked(statement.test, classes)
    if isinstance(statement, ast.If) and isinstance(
        statement.body[-1], (ast.Return, ast.Raise, ast.Continue, ast.Break)
    ):
        return _refuted(statement.test, classes)
    return set()


def private_reads(
    function: ast.AST,
    *,
    self_name: Optional[str],
    defined: set[str],
    modules: set[str],
    allow: set[str],
    classes: KnownClasses | frozenset[str] = KnownClasses(),
    foreign: Optional[set[str]] = None,
) -> list[PrivateRead]:
    """The private attributes ``function``'s body reads from outside, in
    source order (an inner read of a chain first).

    A read of a name in ``defined`` is the class's own business when its
    object is known to be one of ``classes`` (or an instance of one), or
    when ``foreign`` (what the project's other classes define) lacks the
    name; ``foreign=None`` takes ``defined`` by name alone. An
    ``isinstance`` check of a name against ``classes`` makes it known to be
    one where the check holds."""
    if not isinstance(classes, KnownClasses):
        classes = KnownClasses(frozenset(classes))
    body = list(getattr(function, "body", []) or [])
    instances = _instances(function, self_name, classes)
    narrowed = _narrowed(body, classes) if classes.simple else set()

    def own_attribute(read: PrivateRead) -> bool:
        if read.attr not in defined:
            return False
        if foreign is None or read.attr not in foreign:
            return True
        if isinstance(read.value, ast.Name) and (
            (read.value.id, id(read.value)) in narrowed
        ):
            return True
        return _same_class(
            read.value, self_name=self_name, classes=classes, instances=instances
        )

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
        and not own_attribute(read)
        and id(read.node) not in written
        and not _own(read.value, self_name)
        and not (isinstance(read.value, ast.Name) and read.value.id in modules)
    ]
    return sorted(
        found,
        key=lambda r: (r.node.lineno, r.node.col_offset, r.node.end_col_offset or 0),
    )


def _parameter_annotations(function: ast.AST) -> dict[str, Optional[ast.expr]]:
    """Each parameter's annotation, positional parameters first, in order."""
    if not isinstance(function, _FUNCTIONS):
        return {}
    arguments = function.args
    return {
        a.arg: a.annotation
        for a in arguments.posonlyargs + arguments.args + arguments.kwonlyargs
    }


def _parameter_classes(function: ast.AST) -> dict[str, Optional[str]]:
    return {
        name: annotated_class(annotation)
        for name, annotation in _parameter_annotations(function).items()
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
            return build_rule_result(rule, source, target, match, "ERROR", details, ())
        self_name = _first_parameter(function) if target.kind == "method" else None
        scope = _import_scope(target, ctx)
        family = _class_family(_owning_class(target, ctx), ctx, scope)
        reads = private_reads(
            function,
            self_name=self_name,
            defined=family.defined,
            classes=family.names,
            foreign=family.foreign,
            modules=set(scope.modules),
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
    "BINARY_DUNDERS",
    "KnownClasses",
    "MUTATING_METHODS",
    "NAMED_TUPLE_API",
    "PrivateAccessEvaluator",
    "PrivateRead",
    "private_reads",
    "self_assigned",
]
