"""The project's classes: their data attributes and containers, their
project bases, what a constructor keeps, and whether a class is abstract
or can be built without arguments.
"""

from __future__ import annotations

import ast
from typing import Iterator, Mapping, Optional, Sequence

from pythonarchtesting.mutation.project import Module
from pythonarchtesting.util.ast_utils import (
    ABSTRACT_BASES,
    has_abstract_decorator,
    kept_names,
    self_parameter,
)


def call_name(func: ast.expr) -> Optional[str]:
    """``dict`` of ``dict(...)``, ``defaultdict`` of ``collections.defaultdict(...)``."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def top_classes(module: Module) -> Iterator[ast.ClassDef]:
    for node in module.tree.body:
        if isinstance(node, ast.ClassDef):
            yield node


def class_index(modules: list[Module]) -> dict[str, list[ast.ClassDef]]:
    """The top-level classes of the project by name, in module order: a
    name two modules define has two."""
    classes: dict[str, list[ast.ClassDef]] = {}
    for module in modules:
        for node in module.tree.body:
            if isinstance(node, ast.ClassDef):
                classes.setdefault(node.name, []).append(node)
    return classes


def method_names(cls: ast.ClassDef) -> set[str]:
    return {
        n.name
        for n in cls.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def family(
    cls: ast.ClassDef, classes: Mapping[str, list[ast.ClassDef]]
) -> list[ast.ClassDef]:
    """``cls`` and its project bases (each named by one project class only),
    nearest first: the classes whose methods give an object its attributes."""
    found: list[ast.ClassDef] = []
    pending = [cls]
    while pending:
        current = pending.pop(0)
        if any(current is known for known in found):
            continue
        found.append(current)
        for base in current.bases:
            named = classes.get(call_name(base) or "", [])
            if len(named) == 1:
                pending.append(named[0])
    return found


def data_attributes(
    classes: list[ast.ClassDef], bases: Sequence[ast.ClassDef] = ()
) -> list[str]:
    """The data attributes of a project class: its annotated class-level
    fields and what its methods (and those of its project ``bases``) assign
    to ``self.<name>`` (in an unpacking too); never a method."""
    if len(classes) != 1:
        return []  # no class of that name in the project, or several
    (cls,) = classes
    family = [cls, *(b for b in bases if b is not cls)]
    methods = {
        n.name
        for member in family
        for n in member.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    found: list[str] = []
    for node in (n for member in family for n in member.body):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found.append(node.target.id)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self_name = self_parameter(node)
            # Every attribute of self assigned to, also inside an unpacking
            # (``self.x, self.y = v``) or a for/with target.
            found += [
                item.attr
                for item in ast.walk(node)
                if isinstance(item, ast.Attribute)
                and isinstance(item.ctx, ast.Store)
                and isinstance(item.value, ast.Name)
                and item.value.id == self_name
            ]
    return [a for a in dict.fromkeys(found) if a not in methods]


def mangled(owner: str, attribute: str) -> str:
    """``attribute`` as code outside class ``owner`` reads it: a private
    ``__x`` is stored as ``_Owner__x``; any other name stays."""
    if attribute.startswith("__") and not attribute.endswith("__"):
        return f"_{owner.lstrip('_')}{attribute}"
    return attribute


# What a container the owner's constructor creates is, by its first value.
_CONTAINER_CALLS = ("dict", "list", "set")


# Library classes that build a dict.
_DICT_CALLS = ("defaultdict", "Counter", "OrderedDict")


def _container_kind(value: Optional[ast.expr]) -> Optional[str]:
    """``dict``, ``list`` or ``set`` when ``value`` builds one: a display
    (``{}``, ``[]``, ``{1}``), a comprehension, ``dict(...)``, ``list(...)``,
    ``set(...)``, ``defaultdict(...)``, ``Counter(...)``, ``OrderedDict(...)``,
    or a choice one of whose branches does (``x if x is not None else {}``,
    ``x or []``) and none of which is a constant (``[] if x else None`` may
    leave no container); else ``None``."""
    if isinstance(value, (ast.Dict, ast.DictComp)):
        return "dict"
    if isinstance(value, (ast.List, ast.ListComp)):
        return "list"
    if isinstance(value, (ast.Set, ast.SetComp)):
        return "set"
    if isinstance(value, ast.Call):
        name = call_name(value.func)
        if name in _CONTAINER_CALLS:
            return name
        if name in _DICT_CALLS:
            return "dict"
        return None
    branches: list[ast.expr] = []
    if isinstance(value, ast.IfExp):
        branches = [value.body, value.orelse]
    elif isinstance(value, ast.BoolOp):
        branches = list(value.values)
    if any(isinstance(branch, ast.Constant) for branch in branches):
        return None
    kinds = {_container_kind(branch) for branch in branches} - {None}
    return kinds.pop() if len(kinds) == 1 else None


def _is_dataclass(cls: ast.ClassDef) -> bool:
    return any(
        call_name(d.func if isinstance(d, ast.Call) else d) == "dataclass"
        for d in cls.decorator_list
    )


def _field_factory(value: Optional[ast.expr]) -> Optional[str]:
    """``dict``, ``list`` or ``set`` of ``field(default_factory=dict)``."""
    if not (isinstance(value, ast.Call) and call_name(value.func) == "field"):
        return None
    for keyword in value.keywords:
        if keyword.arg == "default_factory" and isinstance(keyword.value, ast.Name):
            factory = keyword.value.id
            if factory in _CONTAINER_CALLS:
                return factory
            if factory in _DICT_CALLS:
                return "dict"
    return None


def containers(cls: ast.ClassDef, bases: Sequence[ast.ClassDef] = ()) -> dict[str, str]:
    """``attribute -> kind`` for the containers the methods of ``cls`` (and
    of its project ``bases``) assign to ``self`` (of a ``@dataclass``, also
    its fields with a container ``default_factory``): first those the
    constructors assign, in the order they assign them, then those another
    method assigns (a game's ``initialize()`` that fills the lists anew). An
    attribute any method of the class assigns anything else (a tuple,
    ``None``) is no container: changing its contents could break the class
    itself."""
    family = [cls, *(b for b in bases if b is not cls)]
    methods = {name for member in family for name in method_names(member)}
    found: list[tuple[int, int, int, int, str, Optional[str]]] = []
    for depth, member in enumerate(family):
        if _is_dataclass(member):
            # A field the generated ``__init__`` fills from its default factory.
            found += [
                (0, depth, node.lineno, node.col_offset, node.target.id, kind)
                for node in member.body
                if isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and (kind := _field_factory(node.value)) is not None
            ]
        for node in member.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            self_name = self_parameter(node)
            later = 0 if node.name == "__init__" else 1
            for item in ast.walk(node):
                if isinstance(item, ast.Assign):
                    targets, value = list(item.targets), item.value
                elif isinstance(item, ast.AnnAssign) and item.value is not None:
                    targets, value = [item.target], item.value
                else:
                    continue
                found += [
                    (
                        later,
                        depth,
                        item.lineno,
                        item.col_offset,
                        t.attr,
                        _container_kind(value),
                    )
                    for t in targets
                    if isinstance(t, ast.Attribute)
                    and isinstance(t.value, ast.Name)
                    and t.value.id == self_name
                ]
    kinds: dict[str, set[Optional[str]]] = {}
    initial: dict[str, str] = {}
    for *_, attribute, kind in sorted(found, key=lambda f: f[:4]):
        kinds.setdefault(attribute, set()).add(kind)
        if kind is not None:
            initial.setdefault(attribute, kind)
    return {a: k for a, k in initial.items() if kinds[a] == {k} and a not in methods}


def kept_parameters(
    method: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Iterator[tuple[ast.stmt, str, ast.Name]]:
    """``kept_names`` whose name is a parameter of ``method`` (but ``self``)."""
    self_name = self_parameter(method)
    params = {
        arg.arg
        for arg in method.args.posonlyargs + method.args.args + method.args.kwonlyargs
    } - {self_name}
    for node, attribute, value in kept_names(method):
        if value.id in params:
            yield node, attribute, value


def _required_parameters(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether a constructor has a parameter without a default, ``self`` aside."""
    args = function.args
    positional = len(args.posonlyargs) + len(args.args) - 1
    return positional > len(args.defaults) or any(d is None for d in args.kw_defaults)


def _required_field(item: ast.stmt) -> bool:
    """Whether a dataclass body statement is a field without a default."""
    if not (isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)):
        return False
    if "ClassVar" in ast.unparse(item.annotation):
        return False
    value = item.value
    if value is None:
        return True
    return (
        isinstance(value, ast.Call)
        and call_name(value.func) == "field"
        and not any(k.arg in ("default", "default_factory") for k in value.keywords)
    )


# Bases that add no constructor parameters.
_PLAIN_BASES = ABSTRACT_BASES | {"object", "Generic", "typing.Generic"}


def needs_arguments(
    cls: ast.ClassDef, classes: Mapping[str, ast.ClassDef], seen: frozenset[str]
) -> Optional[bool]:
    """Whether building ``cls`` needs arguments: its own ``__init__``, its
    dataclass fields, else the first project base that decides; ``None`` when
    a base is no project class the operator knows."""
    for item in cls.body:
        if (
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == "__init__"
        ):
            return _required_parameters(item)
    if _is_dataclass(cls):
        return _required_fields(cls, classes, seen)
    for base in cls.bases:
        name = ast.unparse(base.value if isinstance(base, ast.Subscript) else base)
        if name in _PLAIN_BASES:
            continue
        parent = classes.get(name.rpartition(".")[2])
        if parent is None or parent.name in seen:
            return None
        decided = needs_arguments(parent, classes, seen | {parent.name})
        if decided is not False:
            return decided
    return False


def _project_bases(
    cls: ast.ClassDef, classes: Mapping[str, ast.ClassDef], seen: frozenset[str]
) -> Iterator[ast.ClassDef]:
    """The project classes ``cls`` names as its bases, by their last name."""
    for base in cls.bases:
        name = ast.unparse(base.value if isinstance(base, ast.Subscript) else base)
        parent = classes.get(name.rpartition(".")[2])
        if parent is not None and parent.name not in seen:
            yield parent


def _required_fields(
    cls: ast.ClassDef, classes: Mapping[str, ast.ClassDef], seen: frozenset[str]
) -> bool:
    """Whether a dataclass, or a dataclass it derives from, has a field
    without a default."""
    return any(_required_field(item) for item in cls.body) or any(
        _required_fields(parent, classes, seen | {parent.name})
        for parent in _project_bases(cls, classes, seen)
        if _is_dataclass(parent)
    )


def abstract_left(
    cls: ast.ClassDef, classes: Mapping[str, ast.ClassDef], seen: frozenset[str]
) -> set[str]:
    """The abstract methods ``cls`` declares or inherits from project classes
    and does not implement: with one left, it cannot be built."""
    own = {
        item.name: has_abstract_decorator(item)
        for item in cls.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    inherited: set[str] = set()
    for parent in _project_bases(cls, classes, seen):
        inherited |= abstract_left(parent, classes, seen | {parent.name})
    return {name for name, abstract in own.items() if abstract} | (inherited - set(own))
