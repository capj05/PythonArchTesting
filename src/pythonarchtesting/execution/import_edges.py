from __future__ import annotations

import ast
import fnmatch
from dataclasses import dataclass
from typing import Collection, Iterable, Literal, Sequence

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
    is_top_level: bool


@dataclass(frozen=True)
class NormalizedImportEdge:
    importer_module: str
    imported_module: str
    filepath_rel: str
    lineno: int
    in_type_checking: bool
    is_top_level: bool


def _matches_ignore_globs(
    filepath_rel: str,
    ignore_globs: Sequence[str] | None,
) -> bool:
    return bool(
        ignore_globs
        and any(fnmatch.fnmatch(filepath_rel, pattern) for pattern in ignore_globs)
    )


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
    is_top_level_context: bool = True,
) -> list[ParsedImportReference]:
    references: list[ParsedImportReference] = []
    for child in ast.iter_child_nodes(node):
        child_in_type_checking = in_type_checking
        if isinstance(child, ast.If) and _is_type_checking_test(child.test):
            child_in_type_checking = True
        child_is_top_level_context = is_top_level_context
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            child_is_top_level_context = False

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
                        is_top_level=is_top_level_context,
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
                        is_top_level=is_top_level_context,
                    )
                )

        references.extend(
            collect_import_references_from_node(
                node=child,
                importer_module=importer_module,
                filepath_rel=filepath_rel,
                in_type_checking=child_in_type_checking,
                is_top_level_context=child_is_top_level_context,
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
                is_top_level=ref.is_top_level,
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
                is_top_level=ref.is_top_level,
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
                is_top_level=ref.is_top_level,
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
                is_top_level=ref.is_top_level,
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
    module_entities = collect_canonical_module_entities(
        entities=entities,
        scope_modules=scope_modules,
        ignore_globs=ignore_globs,
    )
    edges: list[NormalizedImportEdge] = []
    for entity in module_entities:
        node = entity.extras["ast_node"]
        edges.extend(
            collect_normalized_import_edges_from_node(
                node=node,
                importer_module=entity.module_path,
                filepath_rel=entity.filepath_rel,
            )
        )
    return sorted(
        edges,
        key=lambda edge: (
            edge.importer_module,
            edge.filepath_rel,
            edge.lineno,
            edge.imported_module,
            edge.in_type_checking,
            edge.is_top_level,
        ),
    )


def collect_canonical_module_entities(
    *,
    entities: Iterable[Entity],
    scope_modules: Collection[str] | None = None,
    ignore_globs: Sequence[str] | None = None,
) -> list[Entity]:
    selected_by_module: dict[str, Entity] = {}
    for entity in entities:
        if scope_modules is not None and entity.module_path not in scope_modules:
            continue
        if _matches_ignore_globs(entity.filepath_rel, ignore_globs):
            continue
        if entity.extras.get("ast_node") is None:
            continue

        existing = selected_by_module.get(entity.module_path)
        if existing is None:
            selected_by_module[entity.module_path] = entity
            continue
        if entity.kind == "module" and existing.kind != "module":
            selected_by_module[entity.module_path] = entity

    return [
        selected_by_module[module_path] for module_path in sorted(selected_by_module)
    ]


__all__: list[str] = []
