"""Views of a model comparison for reports (F3.2–F3.5)."""

from __future__ import annotations

import pytest

from pythonarchtesting.architecture.views import (
    aggregate,
    architectures,
    edges_of,
    matrix,
    metrics,
    static_runtime,
)
from tests.unit.test_report.test_architecture_markdown import (
    _RUNTIME,
    _STATIC,
    _diff,
    _result,
)


def test_malformed_edges_are_skipped():
    assert edges_of({"divergent": ["a -> b", "nonsense"]}, ["divergent"]) == {
        ("a", "b")
    }


def test_matrix_marks_each_edge_by_its_kind():
    found = matrix(
        _diff(
            convergent=["controller -> service"],
            divergent=["controller -> repository"],
            absent=["service -> repository"],
        )
    )

    assert found.modules == ("controller", "repository", "service")
    assert found.cells == {
        ("controller", "service"): "=",
        ("controller", "repository"): "+",
        ("service", "repository"): "-",
    }


def test_static_runtime_splits_the_targets_edges():
    static = {
        "imports": _diff(
            convergent=["controller -> service", "service -> models"],
            divergent=["controller -> json_view"],
        )
    }
    runtime = {
        "calls": _diff(
            convergent=["controller -> service", "service -> repository"],
        ),
        "instances": _diff(divergent=["controller -> repository.Repo"]),
    }

    found = static_runtime(static, runtime)

    assert found.static_only == (
        ("controller", "json_view"),
        ("service", "models"),
    )
    assert found.runtime_only == (
        ("controller", "repository"),
        ("service", "repository"),
    )
    assert found.both == 1
    # The reference calls the repository without importing it: injected.
    assert ("service", "repository") in found.reference_runtime_only
    assert ("controller", "repository") not in found.reference_runtime_only
    assert ("service", "models") in found.reference_static_only


def test_metrics_count_distinct_neighbours():
    found = metrics([("a", "b"), ("a", "c"), ("b", "c"), ("c", "c")])

    assert {m: (v.fan_in, v.fan_out) for m, v in found.items()} == {
        "a": (0, 2),
        "b": (1, 1),
        "c": (2, 0),
    }
    assert found["a"].instability == 1.0
    assert found["b"].instability == pytest.approx(0.5)
    assert found["c"].instability == 0.0


def test_an_isolated_module_has_no_instability():
    assert metrics([("a", "a")]) == {}
    from pythonarchtesting.architecture.views import ModuleMetrics

    assert ModuleMetrics(0, 0).instability is None


def test_aggregate_orders_edges_by_the_share_of_targets():
    shared = {"imports": _diff(divergent=["a -> b"])}
    rare = {"imports": _diff(divergent=["a -> b", "a -> c"], absent=["b -> c"])}

    found = aggregate([{"DEP004": shared}, {"DEP004": shared}, {"DEP004": rare}, {}])

    assert [(s.kind, s.edge, s.targets, s.of) for s in found] == [
        ("divergent", "a -> b", 3, 3),
        ("absent", "b -> c", 1, 3),
        ("divergent", "a -> c", 1, 3),
    ]
    assert found[0].share == 1.0


def test_architectures_by_rule_code():
    other = _result("DEP002/enforce_layers/v1", "OK", {"summary": "fine"})

    assert set(architectures([_STATIC, _RUNTIME, other])) == {"DEP004", "DYN011"}


def test_objects_are_counted_by_the_module_of_their_class():
    instances = _diff(
        convergent=["service -> models.Order"],
        divergent=["service -> models.Receipt", "controller -> Config"],
    )

    found = matrix(instances, "instances")

    assert found.cells == {
        ("service", "models"): "+",
        ("controller", "__init__"): "+",
    }


def test_reference_edges_an_exception_covers_still_count_for_the_reference():
    from pythonarchtesting.architecture.views import REFERENCE, layers_edges

    imports = {
        "convergent": ["ui -> svc"],
        "allowed": ["svc -> repo"],
        "reference": ["svc -> repo", "ui -> svc"],
    }

    assert layers_edges({"imports": imports}, ["imports"], REFERENCE) == {
        ("ui", "svc"),
        ("svc", "repo"),
    }


def test_a_nested_class_is_counted_for_its_module():
    architecture = {
        "calls": _diff(convergent=["svc -> models"]),
        "instances": _diff(convergent=["svc -> models.Outer.Inner"]),
    }

    found = matrix(architecture["instances"], "instances", architecture)

    assert found.cells == {("svc", "models"): "="}


def test_an_undecided_cell_wins_over_an_absent_one():
    found = matrix(
        _diff(absent=["svc -> models.A"], undecided=["svc -> models.B"]),
        "instances",
    )

    assert found.cells == {("svc", "models"): "?"}
