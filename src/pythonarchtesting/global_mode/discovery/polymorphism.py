"""Discovery predicates of ``polymorphism``.

- ``base``: a class with at least one subclass in the project that is
  abstract (``task._interface``: ``ABC``, ``Protocol``, ``ABCMeta``,
  ``@abstractmethod``). A class that is not abstract is a "concrete base
  candidate", bound so that the catalogue reports ``concrete_base`` instead
  of the principle not applying, when it has a subclass and either every
  method but ``__init__`` only raises ``NotImplementedError``, or a subclass
  (direct or not) overrides one of its methods other than ``__init__``.
  One hierarchy has one base, its topmost candidate: a candidate below
  another (an abstract ``Item(Named, ABC)``, a concrete ``Weapon(Item)``) is
  a variant, since the core's ``subclass_of`` needs exactly one base class
  and accepts an indirect subclass. Independent hierarchies keep each of
  their bases; ``split_by_base`` makes one discovery per base of them, from
  the class hierarchy and the calls, not from the reasons' text.
- ``variant``: the subclasses of a base, direct or not, abstract or not,
  found by the base names a class statement lists (``task._base_names``).
- ``client``: a function or method outside the bases and variants that calls
  ``x.m(...)``, ``m`` a polymorphic method of a base or of a candidate
  below it, and ``x`` not ``self`` and no object that is obviously a
  builtin one (``_builtin_object``). A method is polymorphic when it is
  abstract (``is_abstract_method``) or two classes of the hierarchy define
  it: calling a method of the base no variant overrides
  (``scores.update(extra)`` beside an ``Item.update``) is no use of the
  hierarchy. An obviously builtin object is a literal or a comprehension,
  the result of ``dict(...)``, ``list(...)``, ``set(...)``, ``str(...)``
  and the like, a name every assignment of which (in the function, or at
  the top of its module when the function neither assigns it nor takes it
  as a parameter) is one, or ``self.a`` every ``self.a = ...`` of which in
  the class is one (``self.scores = {}``).

A base name is matched to a class of the project by its last name segment,
whatever module the class is in.
"""

from __future__ import annotations

import ast
import dataclasses
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Optional

from pythonarchtesting.entities import Entity
from pythonarchtesting.global_mode.discovery._ast import (
    LITERALS,
    FunctionNode,
    classes,
    functions,
    is_abstract_method,
    local_bindings,
    module_nodes,
    name_of,
    only_raises_not_implemented,
    owner_class,
    project_entities,
)
from pythonarchtesting.global_mode.model import BoundEntity, RoleDiscovery
from pythonarchtesting.principles.task import _base_names, _interface, _methods_of

CONCRETE_BASE = "concrete base candidate"
NOT_FOUND: Mapping[str, str] = {
    "base": (
        "no abstract class (ABC, @abstractmethod) has a subclass in the project, "
        "and no subclass overrides a method of its class"
    ),
    "variant": "no base class has a concrete subclass",
    "client": "no function calls a method of a base class on an object",
}
HIDDEN_BY: Mapping[str, str] = {"base": "not_a_subclass"}
UNATTRIBUTED = "cannot attribute {entity} to a base"


def _concrete_base(node: ast.ClassDef) -> bool:
    methods = [
        item
        for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name != "__init__"
    ]
    return bool(methods) and all(only_raises_not_implemented(m) for m in methods)


def _declared_abstract(node: FunctionNode) -> bool:
    """``is_abstract_method`` but for an undecorated ``pass`` body."""
    if any("abstractmethod" in ast.unparse(d) for d in node.decorator_list):
        return True
    return is_abstract_method(node) and not isinstance(node.body[-1], ast.Pass)


def _own_methods(node: ast.ClassDef) -> set[str]:
    """The methods the class statement defines, ``__init__`` left out."""
    return {
        item.name
        for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name != "__init__"
    }


def _closure(start: str, links: Mapping[str, list[str]]) -> set[str]:
    found: set[str] = set()
    todo = [start]
    while todo:
        for nxt in links.get(todo.pop(), []):
            if nxt != start and nxt not in found:
                found.add(nxt)
                todo.append(nxt)
    return found


@dataclass(frozen=True)
class _Hierarchy:
    """The project's classes by name, their subclass links (a base name
    matched by its last segment) and the base candidates with their reason."""

    nodes: Mapping[str, ast.ClassDef]
    children: Mapping[str, list[str]]
    parents: Mapping[str, list[str]]
    candidates: Mapping[str, str]

    @classmethod
    def of(cls, entities: Sequence[Entity]) -> _Hierarchy:
        every = classes(entities)
        nodes = {name_of(e): node for e, node in every}
        by_simple: dict[str, list[str]] = {}
        for entity, _ in every:
            by_simple.setdefault(entity.qualname.rsplit(".", 1)[-1], []).append(
                name_of(entity)
            )
        children: dict[str, list[str]] = {}
        parents: dict[str, list[str]] = {}
        for entity, node in every:
            name = name_of(entity)
            for base in sorted(_base_names(node)):
                for parent in by_simple.get(base, []):
                    if parent != name:
                        children.setdefault(parent, []).append(name)
                        parents.setdefault(name, []).append(parent)
        hierarchy = cls(nodes, children, parents, {})
        candidates: dict[str, str] = {}
        for name, node in sorted(nodes.items()):
            below = hierarchy.descendants(name)
            if not below:
                continue
            if _interface(node):
                candidates[name] = "abstract class with subclasses"
            elif _concrete_base(node) or any(
                _own_methods(node) & _own_methods(nodes[child]) for child in below
            ):
                candidates[name] = CONCRETE_BASE
        return cls(nodes, children, parents, candidates)

    def descendants(self, name: str) -> set[str]:
        return _closure(name, self.children)

    def ancestors(self, name: str) -> set[str]:
        return _closure(name, self.parents)

    def methods(self, base: str) -> set[str]:
        """The methods of ``base`` and of the candidates below it."""
        found = set(_methods_of(self.nodes[base])) if base in self.nodes else set()
        for below in self.descendants(base):
            if below in self.candidates:
                found |= _methods_of(self.nodes[below])
        return found

    def polymorphic(self, base: str) -> set[str]:
        """The ``methods`` of ``base`` that are polymorphic: declared
        abstract by a class of the hierarchy (``@abstractmethod``, a body
        that only raises ``NotImplementedError`` or is ``...``), or defined
        by two of its classes (the base's own and an override). A ``pass``
        body is a default that does nothing, not a declaration."""
        family = [
            self.nodes[c] for c in {base} | self.descendants(base) if c in self.nodes
        ]
        defined: dict[str, int] = {}
        abstract: set[str] = set()
        for node in family:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined[item.name] = defined.get(item.name, 0) + 1
                    if _declared_abstract(item):
                        abstract.add(item.name)
        return {
            m for m in self.methods(base) if m in abstract or defined.get(m, 0) >= 2
        }


_BUILTIN_MAKERS = frozenset(
    {
        "dict",
        "list",
        "set",
        "frozenset",
        "tuple",
        "str",
        "bytes",
        "bytearray",
        "sorted",
        "defaultdict",
        "OrderedDict",
        "Counter",
        "deque",
    }
)


@dataclass(frozen=True)
class _Scope:
    """What tells whether a receiver in a function is obviously a builtin
    object: the function, the top-level assignments of its module and the
    ``self.a = ...`` assignments of its class."""

    function: Optional[FunctionNode] = None
    module: Mapping[str, list[ast.expr]] = dataclasses.field(default_factory=dict)
    attributes: Mapping[str, list[ast.expr]] = dataclasses.field(default_factory=dict)


def _module_values(tree: ast.Module) -> dict[str, list[ast.expr]]:
    found: dict[str, list[ast.expr]] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    found.setdefault(target.id, []).append(statement.value)
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.value is not None
        ):
            found.setdefault(statement.target.id, []).append(statement.value)
    return found


def _self_values(node: ast.ClassDef) -> dict[str, list[ast.expr]]:
    """``a -> values`` of every ``self.a = <value>`` in the class."""
    found: dict[str, list[ast.expr]] = {}
    for n in ast.walk(node):
        if isinstance(n, ast.Assign):
            for target in n.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    found.setdefault(target.attr, []).append(n.value)
    return found


def _builtin_object(receiver: ast.expr, scope: _Scope) -> bool:
    """Whether ``receiver`` is obviously a builtin object (module
    docstring), never one of the hierarchy."""
    seen: set[str] = set()
    local = local_bindings(scope.function) if scope.function is not None else {}
    params = (
        {a.arg for a in ast.walk(scope.function.args) if isinstance(a, ast.arg)}
        if scope.function is not None
        else set()
    )

    def builtin(value: Optional[ast.expr]) -> bool:
        if value is None:
            return False
        if isinstance(value, LITERALS):
            return True
        if isinstance(value, ast.Call):
            return isinstance(value.func, ast.Name) and value.func.id in _BUILTIN_MAKERS
        if isinstance(value, ast.Name):
            if value.id in seen or value.id in params:
                return False
            seen.add(value.id)
            bound = local.get(value.id) or scope.module.get(value.id) or []
            return bool(bound) and all(builtin(v) for v in bound)
        if (
            isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Name)
            and value.value.id == "self"
        ):
            held = scope.attributes.get(value.attr, [])
            return bool(held) and all(builtin(v) for v in held)
        return False

    return builtin(receiver)


def _calls_on_objects(
    node: ast.AST, methods: set[str], scope: Optional[_Scope] = None
) -> set[str]:
    """The ``methods`` the code under ``node`` calls as ``x.m(...)``, ``x``
    not ``self`` and no obviously builtin object (``_builtin_object``)."""
    scope = scope or _Scope()
    return {
        n.func.attr
        for n in ast.walk(node)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr in methods
        and not (isinstance(n.func.value, ast.Name) and n.func.value.id == "self")
        and not _builtin_object(n.func.value, scope)
    }


def _scopes(entities: Sequence[Entity]) -> dict[str, _Scope]:
    """The ``_Scope`` of every function and method, by name."""
    modules = {module: _module_values(tree) for module, tree in module_nodes(entities)}
    attributes = {
        (e.module_path, e.qualname): _self_values(node) for e, node in classes(entities)
    }
    scopes: dict[str, _Scope] = {}
    for entity, function in functions(entities):
        owner = owner_class(entity)
        scopes[name_of(entity)] = _Scope(
            function,
            modules.get(entity.module_path, {}),
            attributes.get(owner, {}) if owner else {},
        )
    return scopes


def find(entities: Sequence[Entity]) -> dict[str, list[BoundEntity]]:
    """The candidates of ``base``, ``variant`` and ``client`` in ``entities``."""
    tree = _Hierarchy.of(entities)
    bases: list[BoundEntity] = []
    variant_of: dict[str, set[str]] = {}
    base_methods: dict[str, set[str]] = {}
    for name in sorted(tree.candidates):
        if tree.ancestors(name) & set(tree.candidates):
            continue  # a candidate below another one: a variant
        bases.append(BoundEntity(name, "code", tree.candidates[name]))
        for method in tree.polymorphic(name):
            base_methods.setdefault(method, set()).add(name)
        for child in tree.descendants(name):
            variant_of.setdefault(child, set()).add(name)
    variants = [
        BoundEntity(name, "code", "subclass of " + ", ".join(sorted(of)))
        for name, of in sorted(variant_of.items())
    ]

    members = {b.entity for b in bases} | set(variant_of)
    scopes = _scopes(entities)
    clients: list[BoundEntity] = []
    for entity, function in functions(entities):
        owner = owner_class(entity)
        if owner is not None and f"{owner[0]}.{owner[1]}" in members:
            continue
        called = sorted(
            _calls_on_objects(function, set(base_methods), scopes[name_of(entity)])
        )
        if called:
            calls = "; ".join(
                f"{method}() of {', '.join(sorted(base_methods[method]))}"
                for method in called
            )
            clients.append(
                BoundEntity(name_of(entity), "code", f"calls {calls} on an object")
            )
    return {"base": bases, "variant": variants, "client": clients}


def _named_base(why: str, bases: Sequence[str]) -> Optional[str]:
    """The one base ``why`` names by its qualified name, else ``None``."""
    named = [
        base
        for base in bases
        if re.search(rf"(?<![\w.]){re.escape(base)}(?![\w.])", why) is not None
    ]
    return named[0] if len(named) == 1 else None


def split_by_base(
    discovery: RoleDiscovery, entities: Sequence[Entity]
) -> list[RoleDiscovery]:
    """One discovery per base of a polymorphism discovery with several bases
    (independent hierarchies), since the core's ``subclass_of`` needs exactly
    one base class per task. ``entities`` are the ones discovery ran on.

    A variant goes to the part of each base it descends from in the project;
    a client to the part of each base whose methods (``_Hierarchy.methods``)
    it calls on an object. One that neither places (the AI added it) goes to
    the part of the one base its reason names by qualified name; when it
    names none or several, it is in no part and every part lists the
    conflict ``cannot attribute <entity> to a base``. A discovery with at
    most one base is returned as it is."""
    bases = [b.entity for b in discovery.roles.get("base", ())]
    if len(bases) <= 1:
        return [discovery]
    tree = _Hierarchy.of(project_entities(entities))
    nodes = {name_of(e): node for e, node in functions(entities)}
    scopes = _scopes(entities)
    placed: dict[tuple[str, str], set[str]] = {}
    unplaced: set[str] = set()
    for role, bound in discovery.roles.items():
        if role == "base":
            continue
        for b in bound:
            if role == "variant":
                found = tree.ancestors(b.entity) & set(bases)
            elif role == "client" and b.entity in nodes:
                found = {
                    base
                    for base in bases
                    if _calls_on_objects(
                        nodes[b.entity], tree.methods(base), scopes[b.entity]
                    )
                }
            else:
                found = set(bases)  # a role split_by_base does not divide
            if not found and (named := _named_base(b.why, bases)) is not None:
                found = {named}
            if found:
                placed[(role, b.entity)] = found
            else:
                unplaced.add(UNATTRIBUTED.format(entity=b.entity))
    conflicts = tuple(sorted(set(discovery.conflicts) | unplaced))
    parts = []
    for base in discovery.roles["base"]:
        roles: dict[str, tuple[BoundEntity, ...]] = {"base": (base,)}
        for role, bound in discovery.roles.items():
            if role != "base":
                roles[role] = tuple(
                    b for b in bound if base.entity in placed.get((role, b.entity), ())
                )
        missing = next((r for r in ("base", "variant") if not roles.get(r)), None)
        parts.append(
            RoleDiscovery(
                principle=discovery.principle,
                roles=roles,
                conflicts=conflicts,
                not_applied=(
                    f"{missing} not found: {NOT_FOUND[missing]}" if missing else None
                ),
            )
        )
    return parts


__all__ = [
    "CONCRETE_BASE",
    "HIDDEN_BY",
    "NOT_FOUND",
    "UNATTRIBUTED",
    "find",
    "split_by_base",
]
