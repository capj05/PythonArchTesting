"""Operators that break dependency injection: ``rebuild_injected`` and
``hardcode_collaborator``.
"""

from __future__ import annotations

import ast
from typing import Iterator, Optional, Sequence

from pythonarchtesting.mutation.class_model import (
    abstract_left,
    kept_parameters,
    needs_arguments,
    top_classes,
)
from pythonarchtesting.mutation.functions import class_methods
from pythonarchtesting.mutation.imports import class_reference
from pythonarchtesting.mutation.project import Change, Module, Spied
from pythonarchtesting.mutation.source_edit import header_end, insert, replace_span
from pythonarchtesting.util.ast_utils import is_abstract_class


def rebuild_injected(modules: list[Module]) -> Iterator[Change]:
    for module in modules:
        for name, method in class_methods(module.tree):
            if method.name != "__init__":
                continue
            for node, _, value in kept_parameters(method):
                if value.lineno != value.end_lineno:
                    continue
                param = value.id
                source = replace_span(module.text, value, f"type({param})()")
                yield Change(
                    module.file,
                    f"{module.name}: {name} builds its own {param} (line {node.lineno})",
                    source,
                    owner=name.split(".")[0],
                    collaborator=param,
                    line=node.lineno,
                )


def _within(name: str, modules: Sequence[str]) -> bool:
    return any(name == m or name.startswith(f"{m}.") for m in modules)


def hardcode_collaborator(
    modules: list[Module],
    instantiable: Optional[Sequence[str]],
    spied: Optional[Spied] = None,
) -> Iterator[Change]:
    """A constructor builds a collaborator of its own instead of keeping the
    one it was given: ``self.x = x`` (or ``self.x: T = x``) becomes ``self.x
    = C()``, where ``C`` is the first class by name of the ``instantiable``
    modules or classes (every project module by default) that can be built
    without arguments and is no abstract class, nor leaves an inherited
    abstract method unimplemented; never the constructor's own class.
    Without one, nothing. With ``spied`` (``Spied``) only the parameters a
    task gives a spy are hardcoded."""
    classes: dict[str, ast.ClassDef] = {}
    for module in modules:
        for cls in top_classes(module):
            classes.setdefault(cls.name, cls)
    buildable = sorted(
        (cls.name, module.name, module)
        for module in modules
        for cls in top_classes(module)
        if (
            instantiable is None
            or _within(f"{module.name}.{cls.name}".lstrip("."), instantiable)
        )
        and not is_abstract_class(cls)
        and not abstract_left(cls, classes, frozenset({cls.name}))
        and needs_arguments(cls, classes, frozenset({cls.name})) is False
    )
    flat = not any(module.name == "" for module in modules)
    for module in modules:
        for name, method in class_methods(module.tree):
            if method.name != "__init__":
                continue
            owner = name.split(".")[0]
            chosen = next(
                (
                    (cls_name, target)
                    for cls_name, _, target in buildable
                    if not (target is module and cls_name == owner)
                ),
                None,
            )
            if chosen is None:
                continue
            cls_name, target = chosen
            allowed = None if spied is None else spied.get((module.file, owner), ())
            for node, _, value in kept_parameters(method):
                param = value.id
                if allowed is not None and param not in allowed:
                    continue
                reference, line, after = class_reference(module, target, cls_name, flat)
                source = replace_span(module.text, value, f"{reference}()")
                shift = 0
                if line is not None:
                    at = (
                        int(after.end_lineno or after.lineno)
                        if after is not None
                        else header_end(module.tree)
                    )
                    source = insert(source, at, line)
                    shift = 1 if at < node.lineno else 0
                yield Change(
                    module.file,
                    f"{module.name}: {name} builds its own {param} as "
                    f"{cls_name}() (line {node.lineno + shift})",
                    source,
                    owner=owner,
                    collaborator=param,
                    member=cls_name,
                    line=node.lineno + shift,
                    function=name,
                )
