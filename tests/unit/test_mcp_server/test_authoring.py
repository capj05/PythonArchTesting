"""MCP authoring tools: check_cases (F4.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.mcp_server.authoring import check_cases
from pythonarchtesting.mcp_server.errors import ToolInputError

MUTANTS_DIR = Path(__file__).parents[3] / "example" / "architectural_mutants"
REFERENCE = str((MUTANTS_DIR / "reference").resolve())


def _service(prices: list[float]) -> list[Any]:
    return [
        {"id": "A1", "prices": prices},
        {
            "$new": "service.OrderService",
            "args": [
                {"$new": "repository.OrderRepository"},
                {"$new": "pricing.PercentDiscount", "args": [10]},
                {"$new": "events.EventBus"},
            ],
        },
    ]


def _check(cases: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    return check_cases(
        REFERENCE, "controller.handle_order", cases, sandbox="limits", **kwargs
    )


def test_cases_that_run_and_cover_the_entry_are_accepted() -> None:
    result = _check([{"args": _service([10.0])}, {"args": _service([])}])

    assert result["accepted"] is True, result
    assert result["reasons"] == []
    assert [case["status"] for case in result["cases"]] == ["passed", "passed"]
    assert result["coverage"]["ratio"] == 1.0
    assert "controller -> service" in result["edges"]


def test_a_branch_no_case_runs_lowers_coverage_and_is_named() -> None:
    result = _check([{"args": _service([10.0])}], min_coverage=1.0)

    assert result["accepted"] is False
    assert result["coverage"]["ratio"] < 1.0
    assert result["coverage"]["unexercised_lines"]
    assert any("coverage" in reason for reason in result["reasons"])


def test_a_case_that_cannot_be_set_up_is_rejected_with_its_failure() -> None:
    result = _check([{"args": [{"id": "A1"}, {"$new": "service.Missing"}]}])

    assert result["accepted"] is False
    assert result["cases"][0]["status"] == "error"
    assert "Missing" in " ".join(result["cases"][0]["failures"])


@pytest.mark.parametrize(
    ("entry", "cases", "message"),
    [
        ("controller.nowhere", [{"args": []}], "no function"),
        ("controller.handle_order", [], "non-empty"),
        ("controller.handle_order", [{"argz": []}], "argz"),
    ],
)
def test_bad_input_is_a_tool_input_error(
    entry: str, cases: list[dict[str, Any]], message: str
) -> None:
    with pytest.raises(ToolInputError, match=message):
        check_cases(REFERENCE, entry, cases, sandbox="limits")


def test_relative_source_is_rejected() -> None:
    with pytest.raises(ToolInputError):
        check_cases("reference", "controller.handle_order", [{"args": []}])


def test_verify_marker_kills_injection_mutants_with_the_instantiation_marker() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(
        REFERENCE,
        "forbid_runtime_instantiation",
        operators=["rebuild_injected"],
        dynamic=True,
        sandbox="limits",
        detail="all",
    )

    assert result["reference_passes"] is True, result["reference_failing"]
    assert result["total"] >= 1
    killed = {m["description"] for m in result["mutants"] if m["outcome"] == "killed"}
    assert any("builds its own bus" in description for description in killed)


def test_verify_marker_reports_survivors_and_is_then_not_accepted() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(
        REFERENCE, "DEP001", operators=["add_import"], files=["models.py"]
    )

    assert result["reference_passes"] is True
    assert {m["file"] for m in result["mutants"]} == {"models.py"}
    outcomes = {m["outcome"] for m in result["mutants"]}
    assert outcomes <= {"killed", "survived"}
    assert result["accepted"] is (result["survived"] == 0)
    assert result["killed"] + result["survived"] + result["not_run"] == result["total"]


def test_verify_marker_rejects_a_rule_the_reference_does_not_declare() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    with pytest.raises(ToolInputError, match="no rule"):
        verify_marker(REFERENCE, "is_enum", operators=["add_library"], max_mutants=1)


def test_verify_marker_rejects_unknown_operators() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    with pytest.raises(ToolInputError, match="unknown operator"):
        verify_marker(REFERENCE, "DEP001", operators=["shuffle"])


def test_a_skipped_runtime_part_does_not_spoil_a_static_verification() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(
        REFERENCE, "enforce_layers", operators=["add_import"], files=["models.py"]
    )

    # enforce_layers has a runtime part, SKIPPED without dynamic; the static
    # part decides. models importing anything above it breaks the layer order.
    assert result["reference_passes"] is True
    assert result["not_run"] == 0
    assert result["killed"] == result["total"] > 0
    assert result["accepted"] is True


@pytest.mark.parametrize(
    "kwargs",
    [{"files": ["nowhere.py"]}, {"operators": []}, {"files": "models.py"}],
)
def test_verify_marker_refuses_to_judge_without_mutants(kwargs: dict[str, Any]) -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    with pytest.raises(ToolInputError):
        verify_marker(REFERENCE, "DEP001", **kwargs)


def test_verify_marker_files_accept_a_leading_dot_slash() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(
        REFERENCE, "DEP001", operators=["add_import"], files=["./models.py"]
    )

    assert result["total"] > 0


def test_verify_marker_samples_every_operator_when_it_truncates() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(
        REFERENCE,
        "DEP001",
        operators=[
            "add_import",
            "lazy_import",
            "add_library",
            "rebuild_injected",
            "drop_call",
        ],
        files=["service.py", "controller.py", "models.py"],
        max_mutants=10,
    )

    assert {m["operator"] for m in result["mutants"]} == {
        "add_import",
        "lazy_import",
        "add_library",
        "rebuild_injected",
        "drop_call",
    }
    assert result["truncated"] is True
    assert result["accepted"] is False


def test_by_default_only_the_markers_file_and_operators_are_mutated() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(
        REFERENCE, "forbid_runtime_instantiation", dynamic=True, sandbox="limits"
    )

    assert result["scope"]["operators"] == ["rebuild_injected"]
    assert result["scope"]["files"] == ["service.py"]
    assert {m["file"] for m in result["mutants"]} <= {"service.py"}
    assert set(result["by_operator"]) == {"rebuild_injected"}
    assert result["truncated"] is False


def test_a_project_wide_marker_mutates_every_file() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(REFERENCE, "enforce_layers")

    assert result["scope"]["files"] == "all"
    assert result["scope"]["operators"] == ["add_import", "lazy_import"]


def test_a_marker_no_operator_can_break_needs_explicit_operators() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    with pytest.raises(ToolInputError, match="operators"):
        verify_marker(REFERENCE, "is_runtime_singleton")


def test_killed_mutants_are_counted_not_listed_by_default() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    brief = verify_marker(REFERENCE, "enforce_layers")
    full = verify_marker(REFERENCE, "enforce_layers", detail="all")

    assert all(m["outcome"] != "killed" for m in brief["mutants"])
    assert len(full["mutants"]) == full["total"]
    assert brief["by_operator"] == full["by_operator"]
    assert sum(c["killed"] for c in brief["by_operator"].values()) == brief["killed"]


def test_a_runtime_marker_without_dynamic_is_an_input_error() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    with pytest.raises(ToolInputError, match="dynamic"):
        verify_marker(REFERENCE, "forbid_runtime_instantiation")


@pytest.mark.parametrize("value", ["many", None])
def test_non_numeric_limits_are_input_errors(value: Any) -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    with pytest.raises(ToolInputError):
        verify_marker(REFERENCE, "enforce_layers", max_mutants=value)
    with pytest.raises(ToolInputError):
        check_cases(
            REFERENCE, "controller.handle_order", [{"args": []}], min_coverage=value
        )
