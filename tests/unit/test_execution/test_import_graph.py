from __future__ import annotations

from pythonarchtesting.execution.import_edges import NormalizedImportEdge
from pythonarchtesting.execution.import_graph import (
    build_module_dependency_graph,
    filter_module_dependency_graph,
)


def _edge(
    *,
    importer_module: str,
    imported_module: str,
    filepath_rel: str,
    lineno: int,
    in_type_checking: bool = False,
    is_top_level: bool = True,
) -> NormalizedImportEdge:
    return NormalizedImportEdge(
        importer_module=importer_module,
        imported_module=imported_module,
        filepath_rel=filepath_rel,
        lineno=lineno,
        in_type_checking=in_type_checking,
        is_top_level=is_top_level,
    )


def test_build_module_dependency_graph_seeds_internal_and_external_nodes() -> None:
    graph = build_module_dependency_graph(
        internal_modules={
            "assignment.a": "assignment/a.py",
            "assignment.b": "assignment/b.py",
        },
        edges=[
            _edge(
                importer_module="assignment.a",
                imported_module="assignment.b",
                filepath_rel="assignment/a.py",
                lineno=1,
            ),
            _edge(
                importer_module="assignment.b",
                imported_module="requests",
                filepath_rel="assignment/b.py",
                lineno=2,
            ),
        ],
    )

    assert graph.nodes["assignment.a"].is_internal is True
    assert graph.nodes["assignment.b"].is_internal is True
    assert graph.nodes["requests"].is_internal is False
    assert [edge.imported_module for edge in graph.get_outgoing("assignment.b")] == [
        "requests"
    ]


def test_build_module_dependency_graph_deduplicates_exact_duplicate_edges() -> None:
    duplicate_edge = _edge(
        importer_module="assignment.a",
        imported_module="requests",
        filepath_rel="assignment/a.py",
        lineno=10,
    )

    graph = build_module_dependency_graph(
        internal_modules={"assignment.a": "assignment/a.py"},
        edges=[duplicate_edge, duplicate_edge],
    )

    assert graph.get_outgoing("assignment.a") == (duplicate_edge,)


def test_build_module_dependency_graph_preserves_distinct_provenance_and_sorting() -> (
    None
):
    graph = build_module_dependency_graph(
        internal_modules={"assignment.a": "assignment/a.py"},
        edges=[
            _edge(
                importer_module="assignment.a",
                imported_module="requests",
                filepath_rel="assignment/a.py",
                lineno=30,
            ),
            _edge(
                importer_module="assignment.a",
                imported_module="requests",
                filepath_rel="assignment/a.py",
                lineno=10,
            ),
        ],
    )

    assert [
        (edge.imported_module, edge.lineno)
        for edge in graph.get_outgoing("assignment.a")
    ] == [
        ("requests", 10),
        ("requests", 30),
    ]


def test_build_module_dependency_graph_preserves_is_top_level_metadata() -> None:
    graph = build_module_dependency_graph(
        internal_modules={"assignment.a": "assignment/a.py"},
        edges=[
            _edge(
                importer_module="assignment.a",
                imported_module="json",
                filepath_rel="assignment/a.py",
                lineno=1,
                is_top_level=True,
            ),
            _edge(
                importer_module="assignment.a",
                imported_module="requests",
                filepath_rel="assignment/a.py",
                lineno=3,
                is_top_level=False,
            ),
        ],
    )

    top_level_by_import = {
        edge.imported_module: edge.is_top_level
        for edge in graph.get_outgoing("assignment.a")
    }
    assert top_level_by_import == {"json": True, "requests": False}


def test_filter_module_dependency_graph_removes_type_checking_and_local_edges() -> None:
    graph = build_module_dependency_graph(
        internal_modules={"assignment.a": "assignment/a.py"},
        edges=[
            _edge(
                importer_module="assignment.a",
                imported_module="json",
                filepath_rel="assignment/a.py",
                lineno=1,
            ),
            _edge(
                importer_module="assignment.a",
                imported_module="socket",
                filepath_rel="assignment/a.py",
                lineno=2,
                in_type_checking=True,
            ),
            _edge(
                importer_module="assignment.a",
                imported_module="requests",
                filepath_rel="assignment/a.py",
                lineno=3,
                is_top_level=False,
            ),
        ],
    )

    filtered = filter_module_dependency_graph(
        graph,
        ignore_type_checking=True,
        include_local_edges=False,
    )

    assert [edge.imported_module for edge in filtered.get_outgoing("assignment.a")] == [
        "json"
    ]


def test_filter_module_dependency_graph_externalizes_ignored_internal_modules() -> None:
    graph = build_module_dependency_graph(
        internal_modules={
            "assignment.a": "assignment/a.py",
            "assignment.generated.client": "assignment/generated/client.py",
        },
        edges=[
            _edge(
                importer_module="assignment.a",
                imported_module="assignment.generated.client",
                filepath_rel="assignment/a.py",
                lineno=1,
            ),
            _edge(
                importer_module="assignment.generated.client",
                imported_module="requests",
                filepath_rel="assignment/generated/client.py",
                lineno=1,
            ),
        ],
    )

    filtered = filter_module_dependency_graph(
        graph,
        ignore_type_checking=False,
        include_local_edges=False,
        ignored_filepaths={"assignment/generated/client.py"},
    )

    assert filtered.nodes["assignment.generated.client"].is_internal is False
    assert [edge.imported_module for edge in filtered.get_outgoing("assignment.a")] == [
        "assignment.generated.client"
    ]
    assert filtered.get_outgoing("assignment.generated.client") == ()


def test_filter_module_dependency_graph_can_keep_local_edges_when_requested() -> None:
    graph = build_module_dependency_graph(
        internal_modules={"assignment.a": "assignment/a.py"},
        edges=[
            _edge(
                importer_module="assignment.a",
                imported_module="requests",
                filepath_rel="assignment/a.py",
                lineno=3,
                is_top_level=False,
            ),
        ],
    )

    filtered = filter_module_dependency_graph(
        graph,
        ignore_type_checking=False,
        include_local_edges=True,
    )

    assert [edge.imported_module for edge in filtered.get_outgoing("assignment.a")] == [
        "requests"
    ]
