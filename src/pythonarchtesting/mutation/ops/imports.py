"""Operators that add imports: ``add_import``, ``lazy_import``,
``add_library``, ``dynamic_import`` and ``use_private_name``.
"""

from __future__ import annotations

import ast
from typing import Iterator, Sequence

from pythonarchtesting.execution.import_edges import (
    collect_import_references_from_node,
    normalize_import_reference,
)
from pythonarchtesting.mutation.functions import first_function
from pythonarchtesting.mutation.imports import import_line, imported_modules, relative
from pythonarchtesting.mutation.project import Change, Module
from pythonarchtesting.mutation.source_edit import function_insert, header_end, insert


def add_import(modules: list[Module], lazy: bool) -> Iterator[Change]:
    names = {module.name for module in modules}
    for importer in modules:
        imported = imported_modules(importer, names)
        function = first_function(importer.tree, importer.text) if lazy else None
        if lazy and function is None:
            continue
        for target in sorted(names):
            if not target or target == importer.name or target in imported:
                continue
            line = import_line(importer, target)
            who = importer.name or "__init__"
            if lazy and function is not None:
                at, indent = function_insert(function)
                source = insert(importer.text, at, " " * indent + line)
                yield Change(
                    importer.file,
                    f"{who} imports {target} lazily",
                    source,
                    imported=target,
                )
            else:
                at = header_end(importer.tree)
                yield Change(
                    importer.file,
                    f"{who} imports {target}",
                    insert(importer.text, at, line),
                    imported=target,
                )


def add_library(modules: list[Module], libraries: Sequence[str]) -> Iterator[Change]:
    for module in modules:
        if not module.name:
            continue
        for library in libraries:
            used = {
                edge.imported_module.split(".")[0]
                for ref in collect_import_references_from_node(
                    node=module.tree,
                    importer_module=module.name,
                    filepath_rel=module.file,
                )
                for edge in normalize_import_reference(ref)
            }
            if library in used:
                continue
            source = insert(module.text, header_end(module.tree), f"import {library}")
            yield Change(
                module.file,
                f"{module.name} imports {library}",
                source,
                imported=library,
            )


def dynamic_import(modules: list[Module], libraries: Sequence[str]) -> Iterator[Change]:
    """``__import__("<library>")`` at the top of a module's first function: an
    import no static rule sees, run whenever that function runs."""
    for module in modules:
        if not module.name:
            continue
        function = first_function(module.tree, module.text)
        if function is None:
            continue
        at, indent = function_insert(function)
        where = _qualname(module.tree, function)
        for library in libraries:
            yield Change(
                module.file,
                f"{module.name} imports {library} by a computed name in {where}",
                insert(module.text, at, " " * indent + f'__import__("{library}")'),
                imported=library,
                line=at + 1,
            )


def _qualname(
    tree: ast.Module, function: ast.FunctionDef | ast.AsyncFunctionDef
) -> str:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and function in node.body:
            return f"{node.name}.{function.name}"
    return function.name


PRIVATE_HELPER = "_archtest_private"


def use_private_name(
    modules: list[Module],
) -> Iterator[Change]:
    for owner in modules:
        helper = (
            owner.text.rstrip("\n")
            + f"\n\n\ndef {PRIVATE_HELPER}():\n    return None\n"
        )
        for importer in modules:
            if importer.name == owner.name:
                continue
            line = f"from {relative(importer, owner.name)} import {PRIVATE_HELPER}"
            source = insert(importer.text, header_end(importer.tree), line)
            function = first_function(ast.parse(source), source)
            if function is not None:
                # Called where the module's code runs, so a run sees it too.
                at, indent = function_insert(function)
                source = insert(source, at, " " * indent + f"{PRIVATE_HELPER}()")
            who = importer.name or "__init__"
            yield Change(
                importer.file,
                f"{who} calls a private helper of {owner.name or '__init__'}",
                source,
                subject=owner.file,
                also=((owner.file, helper),),
            )
