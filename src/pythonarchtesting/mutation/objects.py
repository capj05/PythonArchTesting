"""Which project class the objects a function uses are of: a parameter, a
local, or an object a module global holds (``world.BAG``).
"""

from __future__ import annotations

import ast
from typing import Mapping, Optional, Sequence

from pythonarchtesting.mutation.class_model import (
    call_name,
    data_attributes,
    family,
    method_names,
)
from pythonarchtesting.mutation.functions import (
    body_nodes,
    called_on,
    parameter_names,
)
from pythonarchtesting.mutation.project import Module
from pythonarchtesting.util.ast_utils import annotated_class, dotted
from pythonarchtesting.util.module_names import project_module_under_package

# The methods of the builtin containers and of ``str``: a parameter on which
# only these are called may be one of them, so its class is not guessed.
_BUILTIN_METHODS = frozenset(
    name
    for kind in (dict, list, set, str, tuple)
    for name in dir(kind)
    if not name.startswith("_")
)


def _held_globals(
    modules: list[Module], classes: Mapping[str, list[ast.ClassDef]]
) -> dict[str, dict[str, ast.ClassDef]]:
    """``module -> {global: class}`` for the module globals that hold an
    object of a project class: one its constructor builds (``BAG = Bag()``)
    or one the annotation names (``current_place: Place = None``). A global
    given objects of two classes holds neither."""
    held: dict[str, dict[str, ast.ClassDef]] = {}
    for module in modules:
        found: dict[str, Optional[str]] = {}
        for node in module.tree.body:
            annotated: Optional[str] = None
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
                annotated = annotated_class(node.annotation)
            else:
                continue
            value = node.value
            built = call_name(value.func) if isinstance(value, ast.Call) else None
            name = next(
                (c for c in (annotated, built) if c and len(classes.get(c, [])) == 1),
                None,
            )
            if name is None:
                continue
            for target in targets:
                found[target] = name if found.get(target, name) == name else None
        held[module.name] = {
            target: classes[name][0] for target, name in found.items() if name
        }
    return held


def global_owners(
    modules: list[Module], classes: Mapping[str, list[ast.ClassDef]], package: str
) -> dict[str, dict[str, ast.ClassDef]]:
    """``file -> {expression: class}``: how the code of each module reaches
    an object of a project class a module global holds: ``world.BAG`` (an
    imported project module), ``BAG`` (imported from it, or a global of the
    module itself)."""
    held = _held_globals(modules, classes)
    names = {module.name for module in modules}
    owners: dict[str, dict[str, ast.ClassDef]] = {}
    for module in modules:
        mine = owners.setdefault(module.file, dict(held.get(module.name, {})))
        parent = module.name if module.is_package else module.name.rpartition(".")[0]
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname is None and "." in alias.name:
                        continue  # ``import a.b`` binds ``a``
                    target = project_module_under_package(alias.name, names, package)
                    found = held.get(target, {}) if target is not None else {}
                    for name, cls in found.items():
                        mine[f"{alias.asname or alias.name}.{name}"] = cls
                continue
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.level:
                parts = parent.split(".") if parent else []
                if node.level - 1 > len(parts):
                    continue
                parts = parts[: len(parts) - (node.level - 1)]
                base: Optional[str] = ".".join(
                    parts + ([node.module] if node.module else [])
                )
            else:
                base = project_module_under_package(node.module or "", names, package)
            if base is None:
                continue
            for alias in node.names:
                bound = alias.asname or alias.name
                full = f"{base}.{alias.name}" if base else alias.name
                if full in names:
                    for name, cls in held.get(full, {}).items():
                        mine[f"{bound}.{name}"] = cls
                elif alias.name in held.get(base, {}):
                    mine[bound] = held[base][alias.name]
    return owners


def owners_in(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    owners: Mapping[str, ast.ClassDef],
) -> dict[str, ast.ClassDef]:
    """The objects held in module globals (``global_owners``) that
    ``function`` reads, by expression, in the order it first reads them; a
    name the function binds itself (a parameter, a local) is none."""
    if not owners:
        return {}
    declared = {
        name
        for node in ast.walk(function)
        if isinstance(node, (ast.Global, ast.Nonlocal))
        for name in node.names
    }
    local = parameter_names(function) | {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }
    local -= declared
    nodes = sorted(
        (
            node
            for node in body_nodes(function)
            if isinstance(node, (ast.Name, ast.Attribute))
            and isinstance(node.ctx, ast.Load)
        ),
        key=lambda node: (node.lineno, node.col_offset),
    )
    found: dict[str, ast.ClassDef] = {}
    for node in nodes:
        text = dotted(node)
        if text is not None and text in owners and text.split(".")[0] not in local:
            found.setdefault(text, owners[text])
    return found


def owner_class(
    classes: dict[str, list[ast.ClassDef]],
    annotation: Optional[ast.expr],
    called: set[str],
    hints: Optional[Mapping[str, str]] = None,
    parameter: str = "",
) -> Optional[ast.ClassDef]:
    """The project class of a parameter. With ``hints`` (what a task's cases
    build for the function's parameters, ``ParameterClasses``), the class
    they build for it, and none for a parameter they build no project object
    for. Without, the one its annotation names; for a parameter without one,
    the one project class that has every method called on it, unless each of
    those is also a method of a builtin container or ``str`` (a ``dict``
    whose ``items()`` is called is no project object)."""
    if hints is not None:
        hinted = classes.get(hints.get(parameter, ""), [])
        return hinted[0] if len(hinted) == 1 else None
    named = classes.get(annotated_class(annotation) or "", [])
    if len(named) == 1:
        return named[0]
    if annotation is not None or not called or called <= _BUILTIN_METHODS:
        return None
    fitting = [
        cls
        for found in classes.values()
        for cls in found
        if called <= method_names(cls)
    ]
    return fitting[0] if len(fitting) == 1 else None


# Values that are no object of a project class: literals, displays,
# comprehensions and computed results.
_BUILTIN_VALUES = (
    ast.Constant,
    ast.JoinedStr,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Set,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.Lambda,
)


def object_class(
    classes: dict[str, list[ast.ClassDef]],
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    obj: str,
    reads: Sequence[str],
    hints: Optional[Mapping[str, str]] = None,
) -> Optional[ast.ClassDef]:
    """The project class of the object a name in ``function`` holds: of a
    parameter as ``owner_class`` finds it; of a local, the class its
    annotation names or every assignment to it builds (``x = Item(...)``),
    none when one assigns it a literal or a computed value (``_BUILTIN_VALUES``)
    other than ``None``: a ``found = None`` before ``found = Item()`` is
    left out when the other assignments agree on one class.
    Else (and without ``hints``), the one project class that has
    every method called on it and every attribute ``reads`` reads of it (a
    data attribute a builtin container lacks: with one, methods such as
    ``add`` tell a project class too). ``None`` for anything else: an
    exception caught (``except ... as e``), a builtin value, an object of an
    unknown class."""
    arguments = function.args
    parameters = {
        a.arg: a for a in arguments.posonlyargs + arguments.args + arguments.kwonlyargs
    }
    called = called_on(function, obj)
    annotation: Optional[ast.expr] = None
    if obj in parameters:
        if hints is not None:
            return owner_class(classes, None, called, hints, obj)
        annotation = parameters[obj].annotation
        if annotated_class(annotation) in ("Any", "object"):
            annotation = None  # says no more than no annotation
        found = owner_class(classes, annotation, called)
        if found is not None or annotation is not None:
            return found
    else:
        values: list[ast.expr] = []
        for node in body_nodes(function):
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == obj
            ):
                annotation = node.annotation
            elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == obj for t in node.targets
            ):
                values.append(node.value)
        if annotation is not None:
            named = classes.get(annotated_class(annotation) or "", [])
            return named[0] if len(named) == 1 else None
        values = [v for v in values if not _is_none(v)] or values
        if any(isinstance(value, _BUILTIN_VALUES) for value in values):
            return None  # a literal, a display, a computed value: no object
        built = {
            named[0].name: named[0]
            for value in values
            if isinstance(value, ast.Call)
            for named in [classes.get(call_name(value.func) or "", [])]
            if len(named) == 1
        }
        if len(built) > 1:
            return None  # given objects of two classes
        if built and all(
            isinstance(v, ast.Call) and call_name(v.func) in built for v in values
        ):
            return next(iter(built.values()))
    if not reads and (not called or called <= _BUILTIN_METHODS):
        return None  # a builtin container's methods tell no project class
    fitting = [
        cls
        for found in classes.values()
        for cls in found
        if called <= method_names(cls)
        and set(reads)
        <= set(data_attributes([cls], family(cls, classes))) | method_names(cls)
    ]
    return fitting[0] if len(fitting) == 1 else None


def _is_none(value: ast.expr) -> bool:
    return isinstance(value, ast.Constant) and value.value is None
