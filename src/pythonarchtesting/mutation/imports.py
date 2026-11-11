"""How the modules of a project import one another: which project modules
a module imports, what its names stand for, and how one module spells an
import of another.
"""

from __future__ import annotations

import ast
from typing import Optional

from pythonarchtesting.execution.import_edges import (
    collect_import_references_from_node,
    normalize_import_reference,
    resolve_relative_module,
)
from pythonarchtesting.execution.module_structure import module_of
from pythonarchtesting.mutation.functions import module_functions
from pythonarchtesting.mutation.project import Module
from pythonarchtesting.util.module_names import project_module_under_package


def imported_modules(module: Module, names: set[str]) -> set[str]:
    """The project modules ``module`` imports anywhere."""
    found: set[str] = set()
    for ref in collect_import_references_from_node(
        node=module.tree, importer_module=module.name, filepath_rel=module.file
    ):
        for edge in normalize_import_reference(ref):
            target = module_of(edge.imported_module, names)
            if target is not None:
                found.add(target)
    return found


def import_line(importer: Module, target: str) -> str:
    """A relative import of the project module ``target`` from ``importer``."""
    depth = len(importer.name.split(".")) if importer.name else 0
    if not importer.is_package:
        depth -= 1
    dots = "." * (depth + 1)
    parent, _, last = target.rpartition(".")
    return f"from {dots}{parent} import {last}"


def relative(importer: Module, target: str) -> str:
    """``target`` spelled relatively from ``importer`` (``.models``, ``..pkg.x``)."""
    depth = len(importer.name.split(".")) if importer.name else 0
    if not importer.is_package:
        depth -= 1
    return "." * (depth + 1) + target


def function_names(module: Module) -> set[str]:
    return {name for name, _ in module_functions(module.tree)}


def project_callables(
    module: Module, by_name: dict[str, Module], package: str = ""
) -> tuple[dict[str, str], dict[str, str]]:
    """What names in ``module`` stand for: ``name -> project module`` of the
    top-level functions it defines or imports (``from .grades import *``
    imports the public ones), and of the project modules it imports
    (``from . import tools``, ``import tools as t``), also under the root
    package's own name (``from game.grades import average``,
    ``import game.grades as gg``; ``project_module_under_package``)."""
    names = set(by_name)
    functions = {name: module.name for name in function_names(module)}
    aliases: dict[str, str] = {}
    for node in ast.walk(module.tree):
        if isinstance(node, ast.ImportFrom):
            base = (
                resolve_relative_module(
                    importer_module=module.name,
                    filepath_rel=module.file,
                    level=node.level,
                    module=node.module,
                )
                if node.level
                else project_module_under_package(node.module or "", names, package)
            )
            if base is None:
                continue  # no project module
            for alias in node.names:
                if alias.name == "*":
                    # ``from .grades import *``: its public top-level functions.
                    if base in by_name:
                        for star in sorted(function_names(by_name[base])):
                            if not star.startswith("_"):
                                functions.setdefault(star, base)
                    continue
                bound = alias.asname or alias.name
                full = f"{base}.{alias.name}" if base else alias.name
                if full in by_name:
                    aliases[bound] = full
                elif base in by_name and alias.name in function_names(by_name[base]):
                    functions[bound] = base
        elif isinstance(node, ast.Import):
            for alias in node.names:
                target = project_module_under_package(alias.name, names, package)
                # ``import a.b`` binds ``a``: only ``as`` binds the module.
                if target is not None and (alias.asname or "." not in alias.name):
                    aliases[alias.asname or alias.name] = target
    return functions, aliases


def class_reference(
    importer: Module, target: Module, name: str, flat: bool = False
) -> tuple[str, Optional[str], Optional[ast.stmt]]:
    """How code of ``importer`` names class ``name`` of ``target``: the
    expression, and the import it needs with the statement to put it after.
    A name the module has already (the class itself, or ``target`` imported
    as a module) needs none; else the import follows the module's own import
    from ``target`` (``from .x import A`` gives ``from .x import B``), or is
    relative; in a ``flat`` project (no package at its root: its modules are
    imported by their own names) absolute."""
    if importer is target:
        return name, None, None
    follow: Optional[ast.ImportFrom] = None
    for node in importer.tree.body:
        if isinstance(node, ast.ImportFrom):
            base = (
                resolve_relative_module(
                    importer_module=importer.name,
                    filepath_rel=importer.file,
                    level=node.level,
                    module=node.module,
                )
                if node.level
                else node.module or ""
            )
            for alias in node.names:
                full = f"{base}.{alias.name}" if base else alias.name
                if base == target.name and alias.name == name:
                    return alias.asname or name, None, None
                if full == target.name:
                    return f"{alias.asname or alias.name}.{name}", None, None
            if base == target.name and follow is None:
                follow = node
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == target.name and (
                    alias.asname or "." not in alias.name
                ):
                    return f"{alias.asname or alias.name}.{name}", None, None
    if follow is not None:
        spec = "." * follow.level + (follow.module or "")
        return name, f"from {spec} import {name}", follow
    if flat:
        return name, f"from {target.name} import {name}", None
    depth = len(importer.name.split(".")) if importer.name else 0
    if not importer.is_package:
        depth -= 1
    return name, f"from {'.' * (depth + 1)}{target.name} import {name}", None
