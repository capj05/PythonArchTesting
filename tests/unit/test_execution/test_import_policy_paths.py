from __future__ import annotations

from pythonarchtesting.execution.import_edges import NormalizedImportEdge
from pythonarchtesting.execution.import_graph import build_module_dependency_graph
from pythonarchtesting.execution.import_policy_paths import (
    collect_reachable_import_violations,
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


def test_collect_reachable_import_violations_avoids_cycles() -> None:
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
                imported_module="assignment.a",
                filepath_rel="assignment/b.py",
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

    violations = collect_reachable_import_violations(
        graph=graph,
        root_modules=["assignment.a"],
        forbidden_prefixes=["requests"],
        allowed_prefixes=[],
    )

    assert len(violations) == 1
    assert violations[0].start_module == "assignment.a"
    assert violations[0].forbidden_target == "requests"
    assert [(step.from_module, step.to_module) for step in violations[0].steps] == [
        ("assignment.a", "assignment.b"),
        ("assignment.b", "requests"),
    ]


def test_collect_reachable_import_violations_preserves_distinct_paths() -> None:
    graph = build_module_dependency_graph(
        internal_modules={
            "assignment.a": "assignment/a.py",
            "assignment.b": "assignment/b.py",
            "assignment.c": "assignment/c.py",
        },
        edges=[
            _edge(
                importer_module="assignment.a",
                imported_module="assignment.b",
                filepath_rel="assignment/a.py",
                lineno=1,
            ),
            _edge(
                importer_module="assignment.a",
                imported_module="assignment.c",
                filepath_rel="assignment/a.py",
                lineno=2,
            ),
            _edge(
                importer_module="assignment.b",
                imported_module="requests",
                filepath_rel="assignment/b.py",
                lineno=3,
            ),
            _edge(
                importer_module="assignment.c",
                imported_module="requests",
                filepath_rel="assignment/c.py",
                lineno=4,
            ),
        ],
    )

    violations = collect_reachable_import_violations(
        graph=graph,
        root_modules=["assignment.a"],
        forbidden_prefixes=["requests"],
        allowed_prefixes=[],
    )

    assert len(violations) == 2
    assert [
        [(step.from_module, step.to_module, step.lineno) for step in violation.steps]
        for violation in violations
    ] == [
        [
            ("assignment.a", "assignment.b", 1),
            ("assignment.b", "requests", 3),
        ],
        [
            ("assignment.a", "assignment.c", 2),
            ("assignment.c", "requests", 4),
        ],
    ]


def test_collect_reachable_import_violations_is_sorted_independent_of_input_order() -> (
    None
):
    graph = build_module_dependency_graph(
        internal_modules={
            "assignment.a": "assignment/a.py",
            "assignment.x": "assignment/x.py",
        },
        edges=[
            _edge(
                importer_module="assignment.x",
                imported_module="requests",
                filepath_rel="assignment/x.py",
                lineno=1,
            ),
            _edge(
                importer_module="assignment.a",
                imported_module="requests",
                filepath_rel="assignment/a.py",
                lineno=1,
            ),
        ],
    )

    violations = collect_reachable_import_violations(
        graph=graph,
        root_modules=["assignment.x", "assignment.a"],
        forbidden_prefixes=["requests"],
        allowed_prefixes=[],
    )

    assert [violation.start_module for violation in violations] == [
        "assignment.a",
        "assignment.x",
    ]
