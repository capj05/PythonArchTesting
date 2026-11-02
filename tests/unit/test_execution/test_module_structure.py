"""Cycles and layer order on a module graph (``execution/module_structure``)."""

from __future__ import annotations

import pytest

from pythonarchtesting.execution.import_edges import NormalizedImportEdge
from pythonarchtesting.execution.module_structure import (
    Layer,
    cycle_path,
    describe_violation,
    import_module_edges,
    layer_violations,
    module_of,
    parse_layers,
    rename_edges,
    strongly_connected,
)


def _edge(
    importer: str, imported: str, line: int = 1, *, type_checking: bool = False
) -> NormalizedImportEdge:
    return NormalizedImportEdge(
        importer_module=importer,
        imported_module=imported,
        filepath_rel=f"{importer or '__init__'}.py",
        lineno=line,
        in_type_checking=type_checking,
        is_top_level=False,
    )


def test_an_imported_name_resolves_to_the_most_specific_module() -> None:
    modules = {"", "pkg", "pkg.sub", "models"}

    assert module_of("models.Order", modules) == "models"
    assert module_of("pkg.sub.Thing", modules) == "pkg.sub"
    assert module_of("requests", modules) is None
    # The root package names only itself, not every module.
    assert module_of("", modules) == ""


def test_import_edges_keep_project_modules_and_lazy_imports() -> None:
    modules = {"service", "models", "pkg", "pkg.sub"}
    edges = [
        _edge("service", "models"),
        _edge("service", "models.Order"),
        _edge("service", "requests"),
        _edge("models", "service", 7),  # inside a function: still an edge
        _edge("service", "typing_only", 3, type_checking=True),
        # from pkg import sub: an edge to pkg.sub, not also to pkg
        _edge("models", "pkg", 9),
        _edge("models", "pkg.sub", 9),
    ]

    graph = import_module_edges(edges, modules)

    assert sorted(graph) == [
        ("models", "pkg.sub"),
        ("models", "service"),
        ("service", "models"),
    ]
    assert graph[("models", "service")].lineno == 7


def test_type_checking_imports_count_when_asked() -> None:
    edges = [_edge("a", "b", type_checking=True)]

    assert import_module_edges(edges, {"a", "b"}) == {}
    assert list(import_module_edges(edges, {"a", "b"}, ignore_type_checking=False))


def test_strongly_connected_finds_every_cycle_and_nothing_else() -> None:
    edges = {
        ("a", "b"),
        ("b", "c"),
        ("c", "a"),
        ("c", "d"),
        ("d", "e"),
        ("e", "d"),
        ("f", "a"),
    }

    assert strongly_connected(edges) == [["a", "b", "c"], ["d", "e"]]
    assert strongly_connected({("a", "b"), ("b", "c")}) == []


def test_strongly_connected_handles_a_long_chain_without_recursion() -> None:
    names = [f"m{index:04d}" for index in range(5000)]
    edges = set(zip(names, names[1:])) | {(names[-1], names[0])}

    (component,) = strongly_connected(edges)

    assert len(component) == 5000


def test_cycle_path_is_closed_and_shortest() -> None:
    edges = {("a", "b"), ("b", "a"), ("b", "c"), ("c", "a")}

    assert cycle_path(["a", "b", "c"], edges) == ["a", "b", "a"]


def test_layers_parse_import_linter_notation() -> None:
    layers = parse_layers(["top", "x | y", "p : q", "bottom"], closed=["x"])

    assert layers == [
        Layer(("top",)),
        Layer(("x", "y"), independent=True, closed=True),
        Layer(("p", "q"), independent=False),
        Layer(("bottom",)),
    ]


@pytest.mark.parametrize(
    ("raw", "closed", "problem"),
    [
        (["a | b : c"], [], "mixes"),
        (["a", "a"], [], "more than one layer"),
        (["a |"], [], "empty module"),
        (["a", "b"], ["c"], "in no layer"),
        (["a", "b"], ["b"], "lowest layer"),
    ],
)
def test_invalid_layers_are_rejected(
    raw: list[str], closed: list[str], problem: str
) -> None:
    with pytest.raises(ValueError, match=problem):
        parse_layers(raw, closed)


_LAYERS = parse_layers(
    ["controller", "service", "repository | events", "models"], closed=["service"]
)


def _kinds(edges: set[tuple[str, str]], *, chains: bool = True) -> list[tuple]:
    return [
        (item.kind, item.path)
        for item in layer_violations(edges, _LAYERS, chains=chains)
    ]


def test_downward_use_through_each_layer_is_allowed() -> None:
    edges = {
        ("controller", "service"),
        ("service", "repository"),
        ("service", "models"),
        ("repository", "models"),
    }

    assert _kinds(edges) == []


def test_upward_sibling_and_bypassing_uses_are_violations() -> None:
    edges = {
        ("models", "service"),
        ("repository", "events"),
        ("controller", "repository"),
        ("controller", "models"),
    }

    assert _kinds(edges) == [
        ("skip", ("controller", "models")),
        ("skip", ("controller", "repository")),
        ("upward", ("models", "service")),
        ("sibling", ("repository", "events")),
    ]


def test_a_chain_through_an_unlayered_module_counts_only_with_chains() -> None:
    edges = {("models", "helpers"), ("helpers", "controller")}

    assert _kinds(edges) == [("upward", ("models", "helpers", "controller"))]
    assert _kinds(edges, chains=False) == []


def test_a_chain_is_not_followed_through_another_layer() -> None:
    # models -> repository is a violation on its own; the chain on to the
    # controller is reported from repository, not again from models.
    edges = {("models", "repository"), ("repository", "controller")}

    assert _kinds(edges) == [
        ("upward", ("models", "repository")),
        ("upward", ("repository", "controller")),
    ]


def test_submodules_belong_to_their_layer() -> None:
    layers = parse_layers(["app", "domain"])
    edges = {("domain.model", "app.views"), ("app.views", "app.forms")}

    found = layer_violations(edges, layers)

    assert [(item.kind, item.path) for item in found] == [
        ("upward", ("domain.model", "app.views"))
    ]


def test_violations_are_described_with_their_chain() -> None:
    (skip,) = layer_violations({("controller", "repository")}, _LAYERS)
    (upward,) = layer_violations({("models", "service")}, _LAYERS)

    assert describe_violation(skip) == (
        "controller -> repository: controller bypasses the closed layer service "
        "to reach repository"
    )
    assert "models is below service" in describe_violation(upward)


def test_renaming_merges_modules_and_drops_loops() -> None:
    edges = {("storage", "models"): 1, ("controller", "service"): 2}
    names = {"storage": "repository", "controller": "app", "service": "app"}

    renamed = rename_edges(edges, lambda module: names.get(module, module))

    assert renamed == {("repository", "models"): 1}


def test_without_chains_only_direct_edges_are_judged_inside_a_package_layer() -> None:
    # booking calls the bus, the bus calls reminders (all one layer), and
    # reminders calls the notifier: only reminders made a call upwards.
    layers = parse_layers(["adapters", "application"])
    edges = {
        ("application.booking", "application.bus"),
        ("application.bus", "application.reminders"),
        ("application.reminders", "adapters.notifier"),
    }

    found = layer_violations(edges, layers, chains=False)

    assert [item.path for item in found] == [
        ("application.reminders", "adapters.notifier")
    ]
    assert all((item.path[0], item.path[-1]) in edges for item in found)
