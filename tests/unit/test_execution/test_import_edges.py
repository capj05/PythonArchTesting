from __future__ import annotations

import ast
from pathlib import Path

from pythonarchtesting.entities import Entity
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.execution.import_edges import (
    NormalizedImportEdge,
    collect_canonical_module_entities,
    collect_normalized_import_edges_for_modules,
    collect_normalized_import_edges_from_node,
)


def _extract_target_entity(
    source_text: str,
    *,
    file_path: str,
    kind: str,
    name: str,
) -> Entity:
    entities = extract_entities_from_source(
        source_text=source_text,
        file_path=Path(file_path),
        root_path=Path("."),
        target_module_name=None,
        role="target",
        include_nested_functions=False,
        root_label="target",
    )
    for entity in entities:
        if entity.kind == kind and entity.name == name:
            return entity
    raise AssertionError(f"Entity '{name}' ({kind}) not found")


def _extract_target_entities(source_text: str, *, file_path: str) -> list[Entity]:
    return extract_entities_from_source(
        source_text=source_text,
        file_path=Path(file_path),
        root_path=Path("."),
        target_module_name=None,
        role="target",
        include_nested_functions=False,
        root_label="target",
    )


def test_collect_normalized_import_edges_from_node_for_simple_import() -> None:
    node = ast.parse("import requests")

    edges = collect_normalized_import_edges_from_node(
        node=node,
        importer_module="assignment.core",
        filepath_rel="assignment/core.py",
    )

    assert edges == [
        NormalizedImportEdge(
            importer_module="assignment.core",
            imported_module="requests",
            filepath_rel="assignment/core.py",
            lineno=1,
            in_type_checking=False,
            is_top_level=True,
        )
    ]


def test_collect_normalized_import_edges_from_node_expands_import_from() -> None:
    node = ast.parse("from requests import sessions")

    edges = collect_normalized_import_edges_from_node(
        node=node,
        importer_module="assignment.core",
        filepath_rel="assignment/core.py",
    )

    assert [edge.imported_module for edge in edges] == [
        "requests",
        "requests.sessions",
    ]


def test_collect_normalized_import_edges_from_node_resolves_relative_imports() -> None:
    node = ast.parse("from .. import utils")

    edges = collect_normalized_import_edges_from_node(
        node=node,
        importer_module="assignment.sub.mod",
        filepath_rel="assignment/sub/mod.py",
    )

    assert [edge.imported_module for edge in edges] == [
        "assignment",
        "assignment.utils",
    ]


def test_collect_normalized_import_edges_from_node_resolves_relative_imports_in_init() -> (
    None
):
    node = ast.parse("from . import utils")

    edges = collect_normalized_import_edges_from_node(
        node=node,
        importer_module="assignment.sub",
        filepath_rel="assignment/sub/__init__.py",
    )

    assert [edge.imported_module for edge in edges] == [
        "assignment.sub",
        "assignment.sub.utils",
    ]


def test_collect_normalized_import_edges_from_node_resolves_multi_level_relative_depth() -> (
    None
):
    node = ast.parse("from ...pkg import mod")

    edges = collect_normalized_import_edges_from_node(
        node=node,
        importer_module="assignment.feature.sub.module",
        filepath_rel="assignment/feature/sub/module.py",
    )

    assert [edge.imported_module for edge in edges] == [
        "assignment.pkg",
        "assignment.pkg.mod",
    ]


def test_collect_normalized_import_edges_from_node_marks_type_checking_imports() -> (
    None
):
    node = ast.parse(
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n"
        "    import socket\n"
    )

    edges = collect_normalized_import_edges_from_node(
        node=node,
        importer_module="assignment.core",
        filepath_rel="assignment/core.py",
    )

    socket_edges = [edge for edge in edges if edge.imported_module == "socket"]
    assert len(socket_edges) == 1
    assert socket_edges[0].in_type_checking is True
    assert socket_edges[0].is_top_level is True


def test_collect_normalized_import_edges_from_node_does_not_expand_wildcard() -> None:
    node = ast.parse("from pkg import *")

    edges = collect_normalized_import_edges_from_node(
        node=node,
        importer_module="assignment.core",
        filepath_rel="assignment/core.py",
    )

    assert [edge.imported_module for edge in edges] == ["pkg"]


def test_collect_normalized_import_edges_marks_function_imports_as_non_top_level() -> (
    None
):
    node = ast.parse("def run():\n" "    import requests\n" "    return 1\n")

    edges = collect_normalized_import_edges_from_node(
        node=node,
        importer_module="assignment.core",
        filepath_rel="assignment/core.py",
    )

    assert len(edges) == 1
    assert edges[0].imported_module == "requests"
    assert edges[0].is_top_level is False


def test_collect_normalized_import_edges_marks_class_body_imports_as_top_level() -> (
    None
):
    node = ast.parse(
        "class Adapter:\n"
        "    import requests\n"
        "\n"
        "    def run(self):\n"
        "        import socket\n"
    )

    edges = collect_normalized_import_edges_from_node(
        node=node,
        importer_module="assignment.core",
        filepath_rel="assignment/core.py",
    )

    top_level_by_module = {edge.imported_module: edge.is_top_level for edge in edges}
    assert top_level_by_module["requests"] is True
    assert top_level_by_module["socket"] is False


def test_collect_normalized_import_edges_for_modules_respects_ignore_globs() -> None:
    kept = _extract_target_entity(
        """
def keep() -> int:
    import requests
    return 1
""",
        file_path="assignment/kept.py",
        kind="function",
        name="keep",
    )
    ignored = _extract_target_entity(
        """
def ignore_me() -> int:
    import socket
    return 1
""",
        file_path="assignment/generated/ignored.py",
        kind="function",
        name="ignore_me",
    )

    edges = collect_normalized_import_edges_for_modules(
        entities=[kept, ignored],
        scope_modules={kept.module_path, ignored.module_path},
        ignore_globs=["assignment/generated/*"],
    )

    assert [edge.imported_module for edge in edges] == ["requests"]


def test_collect_normalized_import_edges_for_modules_double_star_matches_top_level() -> None:
    kept = _extract_target_entity(
        """
def keep() -> int:
    import requests
    return 1
""",
        file_path="assignment/kept.py",
        kind="function",
        name="keep",
    )
    ignored = _extract_target_entity(
        """
def ignore_me() -> int:
    import socket
    return 1
""",
        file_path="ignored_module.py",
        kind="function",
        name="ignore_me",
    )

    edges = collect_normalized_import_edges_for_modules(
        entities=[kept, ignored],
        scope_modules={kept.module_path, ignored.module_path},
        ignore_globs=["**/ignored_module.py"],
    )

    assert [edge.imported_module for edge in edges] == ["requests"]


def test_collect_canonical_module_entities_prefers_module_entity_per_module() -> None:
    entities = _extract_target_entities(
        """
import requests

def run() -> int:
    import socket
    return 1
""",
        file_path="assignment/core.py",
    )

    canonical = collect_canonical_module_entities(
        entities=entities,
        scope_modules={"assignment.core"},
    )

    assert [(entity.kind, entity.module_path) for entity in canonical] == [
        ("module", "assignment.core")
    ]


def test_collect_normalized_import_edges_for_modules_deduplicates_overlapping_entities() -> (
    None
):
    entities = _extract_target_entities(
        """
import requests

def run() -> int:
    import socket
    return 1
""",
        file_path="assignment/core.py",
    )

    edges = collect_normalized_import_edges_for_modules(
        entities=entities,
        scope_modules={"assignment.core"},
    )

    assert [(edge.imported_module, edge.lineno) for edge in edges] == [
        ("requests", 2),
        ("socket", 5),
    ]
