"""Operators that reach into another object's data: ``foreign_write``,
``mutate_private_container``, ``mutate_public_container`` and
``read_private_attribute``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Iterator, Mapping, Optional

from pythonarchtesting.mutation.class_model import (
    containers,
    data_attributes,
    family,
    mangled,
)
from pythonarchtesting.mutation.functions import (
    SIMPLE,
    body_nodes,
    called_on,
    class_methods,
    first_method_call,
    first_use,
    module_functions,
    module_names,
    outside_scopes,
    parameter_names,
)
from pythonarchtesting.mutation.objects import object_class, owner_class, owners_in
from pythonarchtesting.mutation.project import Change, Module, ParameterClasses
from pythonarchtesting.mutation.source_edit import alone, function_insert, insert
from pythonarchtesting.util.ast_utils import is_private, never_runs, self_parameter


@dataclass
class _Use:
    """How a function uses an object it did not get as ``self``."""

    first: ast.stmt  # the first statement that reads it
    change: Optional[ast.stmt] = None  # the first ``x.method(...)`` statement
    reads: list[str] = field(default_factory=list)  # data attributes it reads


def _uses(
    module: Module,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    skip: set[str],
) -> dict[str, _Use]:
    """The objects ``function`` reads attributes of, in order of first use
    in a simple statement (where a write can follow); their data attributes
    are those it reads anywhere in its body (an ``if`` test too) without
    calling them."""
    everywhere = list(body_nodes(function))
    called_anywhere = {id(n.func) for n in everywhere if isinstance(n, ast.Call)}
    data: dict[str, list[str]] = {}
    for node in sorted(
        (
            n
            for n in everywhere
            if isinstance(n, ast.Attribute)
            and isinstance(n.ctx, ast.Load)
            and isinstance(n.value, ast.Name)
            and id(n) not in called_anywhere
        ),
        key=lambda n: (n.lineno, n.col_offset),
    ):
        attrs = data.setdefault(node.value.id, [])  # type: ignore[attr-defined]
        if node.attr not in attrs:
            attrs.append(node.attr)
    uses: dict[str, _Use] = {}
    statements = sorted(
        (node for node in everywhere if isinstance(node, SIMPLE)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    for statement in statements:
        if statement.lineno == function.lineno or not alone(module.text, statement):
            continue  # a one-line function, or a statement sharing its line
        nodes = list(outside_scopes(statement))
        called = {id(n.func) for n in nodes if isinstance(n, ast.Call)}
        reads = sorted(
            (
                node
                for node in nodes
                if isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and isinstance(node.value, ast.Name)
                and node.value.id not in skip
            ),
            key=lambda node: (node.lineno, node.col_offset),
        )
        for read in reads:
            obj = read.value.id  # type: ignore[attr-defined]
            use = uses.setdefault(obj, _Use(statement, reads=list(data.get(obj, []))))
            if id(read) in called and (
                use.change is None
                and isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Call)
                and statement.value.func is read
            ):
                use.change = statement
    return uses


def foreign_write(
    modules: list[Module],
    classes: dict[str, list[ast.ClassDef]],
    owners: Mapping[str, Mapping[str, ast.ClassDef]],
    hints: Optional[ParameterClasses] = None,
) -> Iterator[Change]:
    """``x.a = x.a`` in a method on an object it did not get as ``self`` (in
    a module-level function: on an object it got as a parameter). The value
    stays, but another object's data attribute is assigned from outside its
    class: ``a`` is never a method the code calls, and a private attribute
    (``_stock``) is preferred, among the attributes the function reads and,
    for a parameter annotated with a project class, the data attributes of
    that class. The write follows the first statement that calls a method of
    ``x`` for its effect (``x.remove(...)``), so it runs under the same
    condition as that state change; without one, it follows the first
    statement that reads ``x``. An object a module global holds
    (``world.BAG``, ``global_owners``) is written the same way, with the
    data attributes of its class (and of the class's project bases).
    ``classes`` are the project's classes by name (``class_index``),
    ``owners`` the objects module globals hold (``global_owners``)."""
    for module in modules:
        skip = module_names(module.tree)
        callables = [
            (name, method, self_parameter(method), None)
            for name, method in class_methods(module.tree)
        ] + [
            (name, function, None, parameter_names(function))
            for name, function in module_functions(module.tree)
        ]
        for name, function, self_name, only in callables:
            hinted = None if hints is None else hints.get((module.file, name))
            uses = _uses(module, function, {*skip, *([self_name] if self_name else [])})
            for obj, use in uses.items():
                if only is not None and obj not in only:
                    continue
                cls = object_class(classes, function, obj, use.reads, hinted)
                if cls is None:
                    continue  # no object of a project class: no state to guard
                # A name-mangled ``__x`` of the class is ``_Owner__x`` outside it.
                candidates = use.reads + [
                    mangled(cls.name, a)
                    for a in data_attributes([cls], family(cls, classes))
                    if a not in use.reads
                ]
                if not candidates:
                    continue  # only methods of it are used: nothing to replace
                attribute = next(
                    (a for a in candidates if is_private(a)), candidates[0]
                )
                target = f"{obj}.{attribute}"
                at = use.change or use.first
                line = int(at.end_lineno or at.lineno)
                source = insert(
                    module.text, line, " " * at.col_offset + f"{target} = {target}"
                )
                yield Change(
                    module.file,
                    f"{module.name}: {name} writes {target} (line {line + 1})",
                    source,
                    owner=name.split(".")[0] if self_name is not None else "",
                    member=attribute,
                    line=line + 1,
                    function=name,
                )
            for obj, cls in owners_in(function, owners.get(module.file, {})).items():
                if self_name is not None and cls.name == name.split(".")[0]:
                    continue
                candidates = [
                    mangled(cls.name, a)
                    for a in data_attributes([cls], family(cls, classes))
                ]
                place = first_use(module, function, obj)
                if not candidates or place is None:
                    continue
                attribute = next(
                    (a for a in candidates if is_private(a)), candidates[0]
                )
                target = f"{obj}.{attribute}"
                line = int(place.end_lineno or place.lineno)
                yield Change(
                    module.file,
                    f"{module.name}: {name} writes {target} (line {line + 1})",
                    insert(
                        module.text,
                        line,
                        " " * place.col_offset + f"{target} = {target}",
                    ),
                    owner=cls.name,
                    member=attribute,
                    line=line + 1,
                    function=name,
                )


# The statement that changes a container's contents, by its kind.
CONTAINER_FILLS = {
    "dict": '{target}["__archtest__"] = 0',
    "list": "{target}.append(0)",
    "set": "{target}.add(0)",
}


def mutate_container(
    modules: list[Module],
    classes: dict[str, list[ast.ClassDef]],
    owners: Mapping[str, Mapping[str, ast.ClassDef]],
    private: bool,
    hints: Optional[ParameterClasses] = None,
) -> Iterator[Change]:
    """Right after the first statement of a client function that calls a
    method of an object of a project class (a parameter, never ``self``, or
    one a module global holds: ``world.BAG``), the function changes the
    contents of that object's first private (or public) container: a key in
    a dict, an item appended to a list or added to a set. A method of the
    class itself is no client. ``classes`` and ``owners`` as for
    ``foreign_write``."""
    for module in modules:
        callables = [
            (name, method, self_parameter(method))
            for name, method in class_methods(module.tree)
        ] + [(name, function, None) for name, function in module_functions(module.tree)]
        for name, function, self_name in sorted(callables, key=lambda c: c[1].lineno):
            arguments = function.args
            # (object, its class, whether a module global holds it)
            found: list[tuple[str, ast.ClassDef, bool]] = []
            for arg in arguments.posonlyargs + arguments.args + arguments.kwonlyargs:
                if arg.arg == self_name:
                    continue
                cls = owner_class(
                    classes,
                    arg.annotation,
                    called_on(function, arg.arg),
                    None if hints is None else hints.get((module.file, name)),
                    arg.arg,
                )
                if cls is not None:
                    found.append((arg.arg, cls, False))
            found += [
                (obj, cls, True)
                for obj, cls in owners_in(function, owners.get(module.file, {})).items()
            ]
            for obj, cls, _ in found:
                if self_name is not None and cls.name == name.split(".")[0]:
                    continue
                attributes = [
                    (a, kind)
                    for a, kind in containers(cls, family(cls, classes)).items()
                    if (is_private(a) if private else not a.startswith("_"))
                ]
                statement = first_method_call(module, function, obj)
                if not attributes or statement is None:
                    continue
                attribute, kind = attributes[0]
                attribute = mangled(cls.name, attribute)
                target = f"{obj}.{attribute}"
                line = int(statement.end_lineno or statement.lineno)
                fill = CONTAINER_FILLS[kind].format(target=target)
                yield Change(
                    module.file,
                    f"{module.name}: {name} changes the contents of {target} "
                    f"(line {line + 1})",
                    insert(module.text, line, " " * statement.col_offset + fill),
                    owner=cls.name,
                    member=attribute,
                    line=line + 1,
                    function=name,
                )


def read_private_attribute(
    modules: list[Module],
    classes: dict[str, list[ast.ClassDef]],
    owners: Mapping[str, Mapping[str, ast.ClassDef]],
    hints: Optional[ParameterClasses] = None,
) -> Iterator[Change]:
    """A client function (or a method of another class) reads the first
    private data attribute of an object of a project class it got as a
    parameter, first thing: ``_ = obj._x``; else of one a module global
    holds (``world.BAG``), right after the first statement that uses it, as
    ``foreign_write`` does (a global may still be ``None`` when the function
    starts). Nothing else changes, so the mutant runs as the reference
    does. A function that uses the name ``_`` itself, or has its body on the
    ``def`` line, gives none. ``classes`` and ``owners`` as for
    ``foreign_write``."""
    for module in modules:
        callables = [
            (name, method, self_parameter(method))
            for name, method in class_methods(module.tree)
        ] + [(name, function, None) for name, function in module_functions(module.tree)]
        for name, function, self_name in sorted(callables, key=lambda c: c[1].lineno):
            if (
                function.body[0].lineno == function.lineno
                or never_runs(function)
                or any(
                    isinstance(node, ast.Name) and node.id == "_"
                    for node in ast.walk(function)
                )
            ):
                continue
            arguments = function.args
            # (object, its class, whether a module global holds it)
            found: list[tuple[str, ast.ClassDef, bool]] = []
            for arg in arguments.posonlyargs + arguments.args + arguments.kwonlyargs:
                if arg.arg == self_name:
                    continue
                cls = owner_class(
                    classes,
                    arg.annotation,
                    called_on(function, arg.arg),
                    None if hints is None else hints.get((module.file, name)),
                    arg.arg,
                )
                if cls is not None:
                    found.append((arg.arg, cls, False))
            found += [
                (obj, cls, True)
                for obj, cls in owners_in(function, owners.get(module.file, {})).items()
            ]
            for obj, cls, held in found:
                if self_name is not None and cls.name == name.split(".")[0]:
                    continue
                private = [
                    a
                    for a in data_attributes([cls], family(cls, classes))
                    if is_private(a)
                ]
                if not private:
                    continue
                attribute = mangled(cls.name, private[0])
                target = f"{obj}.{attribute}"
                if held:
                    # After the first use: a global may still be ``None``
                    # when the function starts (until ``initialize()``).
                    place = first_use(module, function, obj)
                    if place is None:
                        continue
                    at, indent = int(place.end_lineno or place.lineno), place.col_offset
                else:
                    at, indent = function_insert(function)
                yield Change(
                    module.file,
                    f"{module.name}: {name} reads {target} (line {at + 1})",
                    insert(module.text, at, " " * indent + f"_ = {target}"),
                    owner=cls.name,
                    member=attribute,
                    line=at + 1,
                    function=name,
                )
                break  # one object per function
