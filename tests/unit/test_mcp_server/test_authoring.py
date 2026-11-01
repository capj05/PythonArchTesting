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


REFERENCE_2 = str(
    (MUTANTS_DIR.parent / "architectural_mutants_2" / "reference").resolve()
)


def test_forbid_runtime_imports_is_verified_with_the_libraries_it_forbids() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(
        REFERENCE, "forbid_runtime_imports", dynamic=True, sandbox="limits"
    )

    assert result["scope"]["operators"] == ["add_library", "dynamic_import"]
    assert result["scope"]["libraries"] == ["pickle", "sqlite3"]
    assert result["scope"]["files"] == ["service.py"]
    # A module-level import of each library is killed; one by a computed name
    # inside a function is not what this marker sees, and the hint says so.
    assert result["total"] == 4
    assert {
        m["operator"] for m in result["mutants"] if m["outcome"] == "killed"
    } == set()  # killed ones are not listed by default
    assert result["killed"] == 2
    assert {m["operator"] for m in result["mutants"]} == {"dynamic_import"}
    assert result["accepted"] is False
    assert any("forbid_runtime_calls" in hint for hint in result["hints"])


def test_module_interface_is_verified_by_reaching_past_it_from_other_modules() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(
        REFERENCE, "module_interface", dynamic=True, sandbox="limits", detail="all"
    )

    assert result["scope"]["operators"] == ["use_private_name"]
    assert result["scope"]["files"] == ["models.py"]
    assert result["total"] >= 1
    assert all(m["file"] != "models.py" for m in result["mutants"])
    assert all("helper of models" in m["description"] for m in result["mutants"])
    assert result["survived"] == 0, result["mutants"]
    assert result["reference_passes"] is True


def test_implements_protocol_is_verified_by_breaking_the_port() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(REFERENCE_2, "implements_protocol", detail="all")

    assert result["scope"]["operators"] == ["break_port"]
    assert result["reference_passes"] is True
    killed = {m["description"] for m in result["mutants"] if m["outcome"] == "killed"}
    assert "adapters_memory: FixedClock.today is renamed" in killed
    assert (
        "adapters_memory: InMemoryLoanStore.find takes a new required parameter"
        in killed
    )


def test_forbid_imports_mutates_only_what_each_file_forbids() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(REFERENCE, "forbid_imports", detail="all")

    forbidden = {
        "controller.py": {"repository"},
        "service.py": {"repository", "pricing", "events", "sqlite3", "pickle"},
    }
    for mutant in result["mutants"]:
        assert mutant["description"].split()[2] in forbidden[mutant["file"]]
    assert result["scope"]["libraries"] == ["pickle", "sqlite3"]
    # Reachable mode does not see an import inside a function: it survives.
    survivors = [
        m["description"] for m in result["mutants"] if m["outcome"] == "survived"
    ]
    # Nor does any static rule see an import by a computed name: the
    # survivors say a runtime marker is needed for them.
    assert survivors == [
        "controller imports repository lazily",
        "service imports pickle by a computed name in OrderService.__init__",
        "service imports sqlite3 by a computed name in OrderService.__init__",
    ]


def test_a_delegation_marker_is_verified_on_its_own_collaborator() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(
        REFERENCE,
        "require_runtime_delegation",
        dynamic=True,
        sandbox="limits",
        detail="all",
    )

    # The spy "discount" is the constructor's second argument: only its
    # apply() is cut out (a spy cannot be rebuilt from its class, so
    # rebuild_injected would not run).
    assert result["scope"]["operators"] == ["drop_call"]
    assert [m["description"] for m in result["mutants"]] == [
        "service: OrderService.place no longer calls self._discount.apply "
        "(line 104, its first argument passed through)",
    ]
    assert result["accepted"] is True


def test_lines_the_cases_never_run_are_reported_as_case_gaps(tmp_path: Path) -> None:
    import shutil

    from pythonarchtesting.mcp_server.authoring import verify_marker

    project = tmp_path / "shop"
    shutil.copytree(MUTANTS_DIR / "solution", project)
    # One case, with prices: the empty-order branch of handle_order never runs.
    (project / "__init__.py").write_text(
        "from typing import Annotated\n"
        "from pythonarchtesting.rules import forbid_cycles\n"
        "__archtest__: Annotated[None, forbid_cycles(\n"
        '    entry="controller.handle_order",\n'
        '    cases=[{"args": [{"id": "A1", "prices": [10.0]},\n'
        '        {"$new": "service.OrderService", "args": [\n'
        '            {"$new": "repository.OrderRepository"},\n'
        '            {"$new": "pricing.PercentDiscount", "args": [10]},\n'
        '            {"$new": "events.EventBus"}]}]}],\n'
        ")]\n",
        encoding="utf-8",
    )

    result = verify_marker(
        str(project),
        "forbid_cycles",
        files=["models.py"],
        dynamic=True,
        sandbox="limits",
    )

    assert [(g["file"], g["lines"]) for g in result["case_gaps"]] == [
        ("controller.py", "10")
    ]
    assert any("check_cases" in hint for hint in result["hints"])


def test_forbid_foreign_writes_is_verified_by_writing_to_a_collaborator() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(
        REFERENCE,
        "forbid_foreign_writes",
        dynamic=True,
        sandbox="limits",
        detail="all",
    )

    assert result["scope"]["operators"] == ["foreign_write"]
    assert result["scope"]["files"] == ["service.py"]
    assert result["reference_passes"] is True
    assert result["total"] >= 1
    assert result["survived"] == 0, result["mutants"]


def test_forbid_foreign_writes_is_verified_only_in_the_methods_it_is_on() -> None:
    from pythonarchtesting.mcp_server.authoring import verify_marker

    result = verify_marker(
        REFERENCE_2,
        "forbid_foreign_writes",
        dynamic=True,
        sandbox="limits",
        detail="all",
    )

    # The marker is on LendingService.give_back; lend() writes no foreign
    # object the marker would watch.
    assert [m["description"].split(" writes ")[0] for m in result["mutants"]] == [
        "application: LendingService.give_back"
    ]
    assert result["accepted"] is True
