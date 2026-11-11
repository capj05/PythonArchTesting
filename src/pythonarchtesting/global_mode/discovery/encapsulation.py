"""Discovery predicates of ``encapsulation``.

- ``owner``: a class with a container attribute, as the core's mutation
  operators find one (``mutation.class_model.containers``): a list, dict or
  set its methods or those of its project bases assign to ``self.<a>``,
  in ``__init__`` or later (a course's ``initialize()``), a comprehension
  or ``defaultdict(...)`` included, or a dataclass field with a container
  ``default_factory``; an attribute some method assigns anything else is
  none. The container must be changed:

  - by a method of the class or of its project bases other than
    ``__init__``: a call of a mutating method of the core
    (``MUTATING_METHODS``: ``append``, ``pop``, ``update``, ``sort``,
    ``popitem``, ...) on ``self.<a>``, an assignment to or ``del`` of a subscript of it, or an
    augmented assignment to it (``self.items += [x]``). A class that changes
    its container only in ``__init__`` is no owner on this ground;
  - or by project code outside the class (another class's method, a
    function, module-level code): one of those calls on ``<expr>.<a>``, or
    an assignment to a subscript of it, ``<expr>`` not the ``self`` of the
    method the code is in. The match is by the attribute name alone, so
    ``state.inventory.items.append(x)`` makes every class with a container
    ``items`` an owner.
- ``client``: every module with a top-level public function, bound whole by
  its path (the owner's own module too), and every public method of a
  project class that is not an owner, except an abstract method (one
  decorated with ``abstractmethod``, or whose body past a docstring only
  raises ``NotImplementedError`` or is ``...`` or ``pass``) and any method
  of an interface class (``ABC``, ``Protocol``, ``ABCMeta``, an
  ``@abstractmethod``), a concrete one included. No case can build the
  object of such a method, so binding it would only leave an entity without
  cases.

The owner only decides whether the principle applies (design § 13 point 4):
the findings are not limited to owner objects, as in the mode with a
reference. A client the AI writes no cases for is left out of the task and
reported unverified, so the client role is not narrowed here.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping, Sequence
from typing import Optional

from pythonarchtesting.entities import Entity
from pythonarchtesting.execution.evaluators.private_access import MUTATING_METHODS
from pythonarchtesting.global_mode.discovery._ast import (
    FunctionNode,
    classes,
    functions,
    interface_classes,
    is_top_level_public,
    module_nodes,
    name_of,
    owner_class,
    runnable_method,
)
from pythonarchtesting.global_mode.model import BoundEntity
from pythonarchtesting.mutation.class_model import containers, family

NOT_FOUND: Mapping[str, str] = {
    "owner": (
        "no class has a list, dict or set attribute that one of its methods "
        "other than __init__, or code outside the class, changes"
    ),
    "client": "no module has a top-level public function and no other class a public method",
}
HIDDEN_BY: Mapping[str, str] = {}
# The forms of a change (``_changes``) that count from outside the class.
_FROM_OUTSIDE = frozenset({"call", "store"})


def _self_name(method: FunctionNode) -> Optional[str]:
    positional = [*method.args.posonlyargs, *method.args.args]
    return positional[0].arg if positional else None


def _is_name(node: ast.AST, name: Optional[str]) -> bool:
    return name is not None and isinstance(node, ast.Name) and node.id == name


def _changes(root: ast.AST) -> Iterator[tuple[ast.expr, str, str]]:
    """``(object, attribute, form)`` of every change of ``<object>.<a>``
    under ``root``: a change call (``call``), a subscript assigned
    (``store``) or deleted (``del``), an augmented assignment (``aug``)."""
    for node in ast.walk(root):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in MUTATING_METHODS
            and isinstance(node.func.value, ast.Attribute)
        ):
            yield node.func.value.value, node.func.value.attr, "call"
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and isinstance(node.value, ast.Attribute)
        ):
            form = "store" if isinstance(node.ctx, ast.Store) else "del"
            yield node.value.value, node.value.attr, form
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Attribute):
            yield node.target.value, node.target.attr, "aug"


def _changed_on_self(method: FunctionNode) -> set[str]:
    """The ``self`` attributes whose contents ``method`` changes."""
    self_name = _self_name(method)
    return {a for obj, a, _ in _changes(method) if _is_name(obj, self_name)}


def _changed_outside(
    entities: Sequence[Entity],
) -> list[tuple[Optional[str], set[str]]]:
    """``(class of the code or None, attributes it changes on another
    object)`` for every function and method and for each module's own
    statements."""
    found: list[tuple[Optional[str], set[str]]] = []
    for entity, node in functions(entities):
        owner = owner_class(entity)
        self_name = _self_name(node) if owner is not None else None
        changed = {
            a
            for obj, a, form in _changes(node)
            if form in _FROM_OUTSIDE and not _is_name(obj, self_name)
        }
        found.append((f"{owner[0]}.{owner[1]}" if owner else None, changed))
    for _, tree in module_nodes(entities):
        for statement in tree.body:
            if not isinstance(
                statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                found.append(
                    (
                        None,
                        {
                            a
                            for _, a, form in _changes(statement)
                            if form in _FROM_OUTSIDE
                        },
                    )
                )
    return found


def _methods(bases: Sequence[ast.ClassDef]) -> dict[str, FunctionNode]:
    """The methods an object of ``bases[0]`` has, nearest class first."""
    found: dict[str, FunctionNode] = {}
    for member in bases:
        for item in member.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.setdefault(item.name, item)
    return found


def _created_in(attribute: str, bases: Sequence[ast.ClassDef]) -> str:
    """Where the container is created (``in __init__``): the first method of the family,
    nearest class first and ``__init__`` before the others, that assigns
    it; else a dataclass field."""
    for member in bases:
        defs = [
            item
            for item in member.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for method in sorted(defs, key=lambda d: d.name != "__init__"):
            self_name = _self_name(method)
            for node in ast.walk(method):
                targets: list[ast.expr] = []
                if isinstance(node, ast.Assign):
                    targets = list(node.targets)
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                if any(
                    isinstance(target, ast.Attribute)
                    and target.attr == attribute
                    and _is_name(target.value, self_name)
                    for target in targets
                ):
                    return (
                        "in __init__"
                        if method.name == "__init__"
                        else f"in {method.name}()"
                    )
    return "as a dataclass field"


def _owner_reason(
    name: str,
    node: ast.ClassDef,
    by_simple: Mapping[str, list[ast.ClassDef]],
    outside: Sequence[tuple[Optional[str], set[str]]],
) -> Optional[str]:
    """Why the class ``name`` is an owner (module docstring), else ``None``."""
    bases = family(node, by_simple)
    methods = _methods(bases)
    reasons = []
    for attribute, kind in sorted(containers(node, bases).items()):
        changers = [
            f"{method}()"
            for method, function in sorted(methods.items())
            if method != "__init__" and attribute in _changed_on_self(function)
        ]
        if changers:
            where = _created_in(attribute, bases)
            reasons.append(
                f"creates {kind} {attribute} {where}, changed by {', '.join(changers)}"
            )
        elif any(cls != name and attribute in changed for cls, changed in outside):
            reasons.append(f"container {attribute} changed from outside the class")
    return "; ".join(reasons) or None


def find(entities: Sequence[Entity]) -> dict[str, list[BoundEntity]]:
    """The candidates of ``owner`` and ``client`` in ``entities``."""
    every_class = classes(entities)
    by_simple: dict[str, list[ast.ClassDef]] = {}
    for entity, node in every_class:
        by_simple.setdefault(entity.qualname.rsplit(".", 1)[-1], []).append(node)
    outside = _changed_outside(entities)
    owners = [
        BoundEntity(name_of(entity), "code", why)
        for entity, node in every_class
        if (why := _owner_reason(name_of(entity), node, by_simple, outside)) is not None
    ]
    owner_names = {b.entity for b in owners}
    every = functions(entities)
    interfaces = interface_classes(entities)
    client: dict[str, BoundEntity] = {}
    for module in sorted({e.module_path for e, _ in every if is_top_level_public(e)}):
        client[module] = BoundEntity(
            module, "code", "module of top-level public functions"
        )
    for entity, function in every:
        owner = owner_class(entity)
        if (
            owner is None
            or entity.qualname.rsplit(".", 1)[-1].startswith("_")
            or not runnable_method(entity, function, interfaces)
        ):
            continue
        cls = f"{owner[0]}.{owner[1]}"
        if cls not in owner_names:
            client[name_of(entity)] = BoundEntity(
                name_of(entity), "code", f"public method of {cls}, not an owner"
            )
    return {"owner": owners, "client": [client[name] for name in sorted(client)]}


__all__ = ["HIDDEN_BY", "NOT_FOUND", "find"]
