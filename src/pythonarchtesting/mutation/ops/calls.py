"""Operators that take calls away: ``drop_call`` and ``stub_role_call``."""

from __future__ import annotations

import ast
from typing import Any, Iterator, Optional

from pythonarchtesting.mutation.class_model import kept_parameters
from pythonarchtesting.mutation.functions import (
    class_methods,
    module_functions,
)
from pythonarchtesting.mutation.imports import function_names, project_callables
from pythonarchtesting.mutation.project import Change, Module
from pythonarchtesting.mutation.source_edit import alone, replace_span, replace_spans
from pythonarchtesting.util.ast_utils import kept_names, self_parameter


def _collaborator(
    call: ast.Call, self_name: Optional[str], given: frozenset[str] = frozenset()
) -> Optional[tuple[str, str, str]]:
    """``(text, attribute, member)`` when ``call`` is ``self.x.m(...)``
    (``("self.x.m", "x", "m")``), or ``self.x(...)`` with ``x`` among the
    ``given`` attributes, which hold what the constructor was given (a
    function passed in): ``("self.x", "x", "")``."""
    func = call.func
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Attribute)
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == self_name
    ):
        return f"{self_name}.{func.value.attr}.{func.attr}", func.value.attr, func.attr
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == self_name
        and func.attr in given
    ):
        return f"{self_name}.{func.attr}", func.attr, ""
    return None


def _collaborator_call(
    node: ast.stmt, self_name: Optional[str], given: frozenset[str] = frozenset()
) -> Optional[tuple[str, str, str]]:
    """``_collaborator`` of the statement ``node`` when it is only that call."""
    if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
        return None
    return _collaborator(node.value, self_name, given)


def _bypass(text: str, call: ast.Call) -> tuple[str, str]:
    """What a nested collaborator call becomes, and how to say it: its first
    argument passed through (``apply(total)`` -> ``total``), else ``None``."""
    first = call.args[0] if call.args else None
    if first is not None and not isinstance(first, ast.Starred):
        segment = ast.get_source_segment(text, first)
        if segment is not None and "\n" not in segment:
            return segment, "its first argument passed through"
    return "None", "None instead"


def _injected(module: Module) -> dict[tuple[str, str], str]:
    """``(class, attribute) -> name`` for ``self.a = name`` (or ``self.a: T =
    name``) in a constructor."""
    found: dict[tuple[str, str], str] = {}
    for name, method in class_methods(module.tree):
        if method.name != "__init__":
            continue
        for _, attribute, value in kept_names(method):
            found[(name.split(".")[0], attribute)] = value.id
    return found


def _given(module: Module) -> set[tuple[str, str]]:
    """``(class, attribute)`` of each attribute a constructor sets to one of
    its parameters: calling it calls what the object was given."""
    return {
        (name.split(".")[0], attribute)
        for name, method in class_methods(module.tree)
        if method.name == "__init__"
        for _, attribute, _ in kept_parameters(method)
    }


def drop_call(modules: list[Module]) -> Iterator[Change]:
    for module in modules:
        injected = _injected(module)
        given_attributes = _given(module)
        for name, method in class_methods(module.tree):
            self_name = self_parameter(method)
            owner = name.split(".")[0]
            given = frozenset(a for o, a in given_attributes if o == owner)

            def about(
                call: ast.Call,
                found: tuple[str, str, str],
                owner: str = owner,
                name: str = name,
            ) -> dict[str, Any]:
                _, attribute, member = found
                return {
                    "owner": owner,
                    "collaborator": injected.get(
                        (owner, attribute), attribute.lstrip("_")
                    ),
                    "member": member,
                    "line": call.lineno,
                    "function": name,
                }

            found: list[tuple[int, int, Change]] = []
            statements: set[int] = set()
            for node in ast.walk(method):
                if not isinstance(node, ast.stmt):
                    continue
                collaborator = _collaborator_call(node, self_name, given)
                if collaborator is None:
                    continue
                call = collaborator[0]
                statements.add(id(node.value))  # type: ignore[attr-defined]
                if not alone(module.text, node):
                    continue  # sharing its line, it cannot be cut out cleanly
                lines = module.text.splitlines(keepends=True)
                first, last = node.lineno - 1, int(node.end_lineno or node.lineno)
                lines[first:last] = [" " * node.col_offset + "pass\n"]
                found.append(
                    (
                        node.lineno,
                        node.col_offset,
                        Change(
                            module.file,
                            f"{module.name}: {name} no longer calls {call} "
                            f"(line {node.lineno})",
                            "".join(lines),
                            **about(
                                node.value,  # type: ignore[attr-defined]
                                collaborator,
                            ),
                        ),
                    )
                )
            # A call whose result is used (``x = self.d.apply(x)``): the
            # collaborator is bypassed, its argument taken as the result.
            for node in ast.walk(method):
                if not isinstance(node, ast.Call) or id(node) in statements:
                    continue
                collaborator = _collaborator(node, self_name, given)
                if collaborator is None or node.lineno != node.end_lineno:
                    continue
                call = collaborator[0]
                replacement, how = _bypass(module.text, node)
                found.append(
                    (
                        node.lineno,
                        node.col_offset,
                        Change(
                            module.file,
                            f"{module.name}: {name} no longer calls {call} "
                            f"(line {node.lineno}, {how})",
                            replace_span(module.text, node, replacement),
                            **about(node, collaborator),
                        ),
                    )
                )
            for _, _, change in sorted(found, key=lambda item: item[:2]):
                yield change


STUB = "(lambda *a, **k: None)"


def stub_role_call(modules: list[Module], package: str = "") -> Iterator[Change]:
    """A function or method calls no function of one project module any
    more: each such call's function becomes ``(lambda *a, **k: None)``, its
    arguments still evaluated. One mutant per function and module
    (``member``); task verification (``principles.task_mutants``) keeps those of a module
    the check names."""
    by_name = {module.name: module for module in modules}
    for module in modules:
        functions, aliases = project_callables(module, by_name, package)
        callables = list(class_methods(module.tree)) + list(
            module_functions(module.tree)
        )
        for name, function in sorted(callables, key=lambda item: item[1].lineno):
            calls: dict[str, list[ast.expr]] = {}
            for item in function.body:
                for node in ast.walk(item):
                    if not isinstance(node, ast.Call):
                        continue
                    func = node.func
                    target = None
                    if isinstance(func, ast.Name):
                        target = functions.get(func.id)
                    elif (
                        isinstance(func, ast.Attribute)
                        and isinstance(func.value, ast.Name)
                        and func.value.id in aliases
                        and func.attr in function_names(by_name[aliases[func.value.id]])
                    ):
                        target = aliases[func.value.id]
                    if target is not None and func.lineno == func.end_lineno:
                        calls.setdefault(target, []).append(func)
            for target, funcs in sorted(calls.items()):
                line = min(func.lineno for func in funcs)
                yield Change(
                    module.file,
                    f"{module.name}: {name} no longer calls into "
                    f"{target or '__init__'} (line {line})",
                    replace_spans(module.text, funcs, STUB),
                    member=target,
                    line=line,
                    function=name,
                )
