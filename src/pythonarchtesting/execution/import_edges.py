from __future__ import annotations

import ast
import fnmatch
from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

from pythonarchtesting.entities import Entity


@dataclass(frozen=True)
class ParsedImportReference:
    kind: Literal["import", "importfrom"]
    importer_module: str
    filepath_rel: str
    lineno: int
    module: str
    name: str | None
    in_type_checking: bool


@dataclass(frozen=True)
class NormalizedImportEdge:
    importer_module: str
    imported_module: str
    filepath_rel: str
    lineno: int
    in_type_checking: bool


def _resolve_relative_module(
    *,
    importer_module: str,
    filepath_rel: str,
    level: int,
    module: str | None,
) -> str:
    importer_parts = importer_module.split(".") if importer_module else []
    is_package_module = filepath_rel.endswith("/__init__.py")
    if is_package_module:
        context_parts = importer_parts
    else:
        context_parts = importer_parts[:-1]
    remove_parts = max(level - 1, 0)
    if remove_parts > len(context_parts):
        base_parts: list[str] = []
    else:
        base_parts = context_parts[: len(context_parts) - remove_parts]
    if module:
        base_parts.extend(part for part in module.split(".") if part)
    return ".".join(base_parts)


def _is_type_checking_test(test: ast.AST) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return (
            isinstance(test.value, ast.Name)
            and test.value.id == "typing"
            and test.attr == "TYPE_CHECKING"
        )
    return False


def collect_import_references_from_node(
    *,
    node: ast.AST,
    importer_module: str,
    filepath_rel: str,
    in_type_checking: bool = False,
) -> list[ParsedImportReference]:
    references: list[ParsedImportReference] = []
    for child in ast.iter_child_nodes(node):
        child_in_type_checking = in_type_checking
        if isinstance(child, ast.If) and _is_type_checking_test(child.test):
            child_in_type_checking = True

        if isinstance(child, ast.Import):
            for alias in child.names:
                if not alias.name:
                    continue
                references.append(
                    ParsedImportReference(
                        kind="import",
                        importer_module=importer_module,
                        filepath_rel=filepath_rel,
                        lineno=getattr(child, "lineno", 0),
                        module=alias.name,
                        name=None,
                        in_type_checking=child_in_type_checking,
                    )
                )
        elif isinstance(child, ast.ImportFrom):
            prefix = "." * (getattr(child, "level", 0) or 0)
            module = prefix + (child.module or "")
            for alias in child.names:
                references.append(
                    ParsedImportReference(
                        kind="importfrom",
                        importer_module=importer_module,
                        filepath_rel=filepath_rel,
                        lineno=getattr(child, "lineno", 0),
                        module=module,
                        name=alias.name,
                        in_type_checking=child_in_type_checking,
                    )
                )

        references.extend(
            collect_import_references_from_node(
                node=child,
                importer_module=importer_module,
                filepath_rel=filepath_rel,
                in_type_checking=child_in_type_checking,
            )
        )
    return references


def normalize_import_reference(
    ref: ParsedImportReference,
) -> list[NormalizedImportEdge]:
    if ref.kind == "import":
        if not ref.module:
            return []
        return [
            NormalizedImportEdge(
                importer_module=ref.importer_module,
                imported_module=ref.module,
                filepath_rel=ref.filepath_rel,
                lineno=ref.lineno,
                in_type_checking=ref.in_type_checking,
            )
        ]

    level = 0
    while level < len(ref.module) and ref.module[level] == ".":
        level += 1
    module_name = ref.module[level:] if level > 0 else ref.module
    base_module = (
        _resolve_relative_module(
            importer_module=ref.importer_module,
            filepath_rel=ref.filepath_rel,
            level=level,
            module=module_name if module_name else None,
        )
        if level > 0
        else module_name
    )

    edges: list[NormalizedImportEdge] = []
    if base_module:
        edges.append(
            NormalizedImportEdge(
                importer_module=ref.importer_module,
                imported_module=base_module,
                filepath_rel=ref.filepath_rel,
                lineno=ref.lineno,
                in_type_checking=ref.in_type_checking,
            )
        )
    if ref.name and ref.name != "*" and base_module:
        edges.append(
            NormalizedImportEdge(
                importer_module=ref.importer_module,
                imported_module=f"{base_module}.{ref.name}",
                filepath_rel=ref.filepath_rel,
                lineno=ref.lineno,
                in_type_checking=ref.in_type_checking,
            )
        )
    elif ref.name and ref.name != "*" and not base_module:
        edges.append(
            NormalizedImportEdge(
                importer_module=ref.importer_module,
                imported_module=ref.name,
                filepath_rel=ref.filepath_rel,
                lineno=ref.lineno,
                in_type_checking=ref.in_type_checking,
            )
        )
    return edges


def collect_normalized_import_edges_from_node(
    *,
    node: ast.AST,
    importer_module: str,
    filepath_rel: str,
) -> list[NormalizedImportEdge]:
    refs = collect_import_references_from_node(
        node=node,
        importer_module=importer_module,
        filepath_rel=filepath_rel,
    )
    edges: list[NormalizedImportEdge] = []
    for ref in refs:
        edges.extend(normalize_import_reference(ref))
    return edges


def collect_normalized_import_edges_for_modules(
    *,
    entities: Iterable[Entity],
    scope_modules: set[str] | frozenset[str],
    ignore_globs: Sequence[str] | None = None,
) -> list[NormalizedImportEdge]:
    edges: list[NormalizedImportEdge] = []
    for entity in entities:
        if entity.module_path not in scope_modules:
            continue
        if ignore_globs and any(
            fnmatch.fnmatch(entity.filepath_rel, pattern) for pattern in ignore_globs
        ):
            continue
        node = entity.extras.get("ast_node")
        if node is None:
            continue
        edges.extend(
            collect_normalized_import_edges_from_node(
                node=node,
                importer_module=entity.module_path,
                filepath_rel=entity.filepath_rel,
            )
        )
    return edges


__all__: list[str] = []
