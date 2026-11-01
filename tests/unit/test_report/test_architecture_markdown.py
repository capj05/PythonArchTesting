"""The architecture section of the Markdown report (F3.1)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from pythonarchtesting.report.renderers.architecture import (
    across_targets_lines,
    architecture_lines,
    undecided_lines,
)


def _diff(**lists: list[str]) -> dict[str, list[str]]:
    empty: dict[str, list[str]] = {
        "convergent": [],
        "divergent": [],
        "absent": [],
        "undecided": [],
        "allowed": [],
    }
    return {**empty, **lists}


def _result(rule_id: str, status: str, details: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(rule_id=rule_id, status=status, details=details)


_STATIC = _result(
    "DEP004/architecture_entry/v1",
    "FAILED",
    {
        "policy": "allow_new_modules",
        "summary": "import controller -> repository is not in the reference",
        "architecture": {
            "imports": _diff(
                convergent=["controller -> service", "service -> models"],
                divergent=["controller -> repository"],
            ),
            "external": _diff(convergent=["repository -> json"]),
        },
    },
)
_RUNTIME = _result(
    "DYN011/architecture_entry/v1",
    "OK",
    {
        "policy": "layered",
        "summary": "2 case(s) used only the reference's dependencies",
        "architecture": {
            "calls": _diff(
                convergent=["controller -> service"],
                absent=["service -> events"],
                undecided=["controller -> models"],
            ),
            "instances": _diff(undecided=["service -> receipts.Receipt"]),
            "external": _diff(),
        },
        "undecided": [
            "calls: controller -> models",
            "instances: service -> receipts.Receipt",
        ],
    },
)


def test_no_architecture_results_render_nothing():
    other = _result("DEP002/enforce_layers/v1", "OK", {"summary": "fine"})

    assert architecture_lines([other]) == []
    assert undecided_lines([other]) == []


def test_each_rule_gets_a_count_table_per_layer():
    text = "\n".join(architecture_lines([_RUNTIME, _STATIC]))

    assert "## Architecture" in text
    assert "### Static (DEP004): FAILED" in text
    assert "### Runtime (DYN011): OK" in text
    assert "- Policy: `allow_new_modules`" in text
    assert text.index("### Static") < text.index("### Runtime")
    assert "| imports | 2 | 1 | 0 | 0 | 0 |" in text
    assert "| calls | 1 | 0 | 1 | 1 | 0 |" in text


def test_divergent_undecided_and_absent_edges_are_listed_by_layer():
    text = "\n".join(architecture_lines([_STATIC, _RUNTIME]))

    assert "- Divergent (violations): imports `controller -> repository`" in text
    assert (
        "- Undecided (to review): calls `controller -> models`; "
        "instances `service -> receipts.Receipt`"
    ) in text
    assert "- Absent: calls `service -> events`" in text
    # Convergent edges are counted, not listed: they are what is expected.
    assert "`controller -> service`" not in text


def test_long_edge_lists_are_capped():
    many = _result(
        "DEP004/architecture_entry/v1",
        "FAILED",
        {
            "architecture": {
                "imports": _diff(divergent=[f"m{i} -> n" for i in range(30)])
            }
        },
    )

    text = "\n".join(architecture_lines([many]))

    assert "`m0 -> n`" in text
    assert "(+10 more)" in text


def test_undecided_count_line_counts_passes_with_undecided_changes():
    assert undecided_lines([_STATIC, _RUNTIME]) == [
        "- Passed With Undecided Architecture Changes: 1 (see `details.undecided`)"
    ]


def test_each_internal_layer_gets_a_dependency_matrix():
    text = "\n".join(architecture_lines([_STATIC, _RUNTIME]))

    assert "#### Dependency Matrix: imports" in text
    assert "| Module | `controller` | `models` | `repository` | `service` |" in text
    assert "| `controller` |  |  | + | = |" in text
    assert "| `service` |  | = |  |  |" in text
    assert "#### Dependency Matrix: instances" in text
    assert "| Module | `receipts` | `service` |" in text
    assert "| `service` | ? |  |" in text
    # Libraries join a module and a package: no module matrix for them.
    assert "#### Dependency Matrix: external" not in text


def test_large_matrices_are_left_out():
    many = _result(
        "DEP004/architecture_entry/v1",
        "OK",
        {
            "architecture": {
                "imports": _diff(convergent=[f"m{i} -> n" for i in range(20)])
            }
        },
    )

    text = "\n".join(architecture_lines([many]))

    assert "- Dependency matrix of imports left out: 21 modules" in text
    assert "| Module | `m0` |" not in text


def test_module_metrics_are_informative_and_compare_both_sides():
    text = "\n".join(architecture_lines([_STATIC]))

    assert "#### Module Metrics (informative, not part of the verdict)" in text
    assert (
        "| Module | Fan-in (reference / target) | Fan-out (reference / target) "
        "| Instability (reference / target) |"
    ) in text
    assert "| `controller` | 0 / 0 | 1 / 2 | 1.00 / 1.00 |" in text
    assert "| `repository` | 0 / 1 | 0 / 0 | n/a / 0.00 |" in text


def test_static_and_runtime_edges_of_the_target_are_compared():
    static = _result(
        "DEP004/architecture_entry/v1",
        "OK",
        {
            "architecture": {
                "imports": _diff(
                    convergent=["controller -> service", "service -> models"]
                )
            }
        },
    )
    runtime = _result(
        "DYN011/architecture_entry/v1",
        "OK",
        {
            "architecture": {
                "calls": _diff(
                    convergent=["controller -> service", "service -> repository"]
                ),
                "instances": _diff(divergent=["controller -> repository.Repo"]),
            }
        },
    )

    text = "\n".join(architecture_lines([runtime, static]))

    assert "### Static vs Runtime" in text
    assert "- Imported and used at run time: 1" in text
    assert "- Imported only: `service -> models` (also in the reference)" in text
    assert (
        "- At run time only: `controller -> repository`; "
        "`service -> repository` (also in the reference)"
    ) in text


def test_static_vs_runtime_needs_both_rules():
    assert "### Static vs Runtime" not in "\n".join(architecture_lines([_STATIC]))


def _target(*results: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(results=list(results))


def _divergent(*edges: str) -> SimpleNamespace:
    return _result(
        "DEP004/architecture_entry/v1",
        "FAILED",
        {"architecture": {"imports": _diff(divergent=list(edges))}},
    )


def test_edges_shared_across_targets_are_ranked():
    targets = [
        _target(_divergent("a -> b")),
        _target(_divergent("a -> b", "a -> c")),
        _target(_divergent("a -> b", "a -> c")),
        _target(_divergent("x -> y")),
    ]

    text = "\n".join(across_targets_lines(targets))

    assert "## Architecture Across Targets" in text
    assert "| Static (DEP004) | imports | divergent | `a -> b` | 3/4 (75%) |  |" in text
    assert "| `a -> c` | 2/4 (50%) |" in text
    # An edge of one target only is no pattern of the class.
    assert "`x -> y`" not in text


def test_an_edge_nearly_every_target_diverges_on_points_at_the_model():
    targets = [_target(_divergent("a -> b")) for _ in range(3)]

    text = "\n".join(across_targets_lines(targets))

    assert "| `a -> b` | 3/3 (100%) | check the model |" in text


def test_aggregation_needs_two_targets_with_a_comparison():
    assert across_targets_lines([_target(_divergent("a -> b")), _target()]) == []
    assert (
        across_targets_lines(
            [_target(_divergent("a -> b")), _target(_divergent("c -> d"))]
        )
        == []
    )


def test_more_shared_edges_than_listed_end_the_table_first():
    edges = [f"m{i} -> n{i}" for i in range(22)]
    targets = [_target(_divergent(*edges)) for _ in range(3)]

    lines = across_targets_lines(targets)

    at = lines.index("(+2 more)")
    assert lines[at - 1] == ""


def test_only_divergent_and_absent_edges_point_at_the_model():
    undecided = _result(
        "DEP004/architecture_entry/v1",
        "OK",
        {"architecture": {"imports": _diff(undecided=["a -> b"])}},
    )

    text = "\n".join(across_targets_lines([_target(undecided) for _ in range(3)]))

    assert "| `a -> b` | 3/3 (100%) |  |" in text


def test_module_names_are_code_in_matrices_and_metrics():
    root = _result(
        "DEP004/architecture_entry/v1",
        "OK",
        {"architecture": {"imports": _diff(convergent=["app -> __init__"])}},
    )

    text = "\n".join(architecture_lines([root]))

    assert "| Module | `__init__` | `app` |" in text
    assert "| `app` |  | = |" not in text
    assert "| `app` | = |  |" in text
    assert "| `__init__` | 1 / 1 |" in text
