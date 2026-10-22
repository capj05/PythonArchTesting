"""CLI-level tests for the opt-in ``--dynamic`` mode."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pythonarchtesting.cli import main

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHOWCASE = _REPO_ROOT / "example" / "rule_showcase"
_CASE = _SHOWCASE / "dyn001_layers"


def _rule_rows(report: dict) -> list[dict]:
    rows: list[dict] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if node.get("rule_id", "").startswith("DYN") and "status" in node:
                rows.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(report)
    return rows


def _run(
    target: str, tmp_path: Path, *extra: str, case: Path = _CASE
) -> tuple[int, list[dict]]:
    output = tmp_path / "report.json"
    exit_code = main(
        [
            "--source",
            str(case / "reference"),
            "--target",
            str(case / "assignments" / target),
            "--format",
            "json",
            "--output",
            str(output),
            *extra,
        ]
    )
    return exit_code, _rule_rows(json.loads(output.read_text(encoding="utf-8")))


@pytest.fixture(autouse=True)
def _repo_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(_REPO_ROOT)


def test_without_dynamic_the_rules_are_skipped_and_the_target_passes(
    tmp_path: Path, capsys
) -> None:
    exit_code, rows = _run("target_fail_bypass_service", tmp_path)
    capsys.readouterr()

    assert exit_code == 0
    assert rows
    assert {row["status"] for row in rows} == {"SKIPPED"}


def test_without_dynamic_a_missing_target_entity_does_not_fail_the_run(
    tmp_path: Path, capsys
) -> None:
    target = tmp_path / "target_missing"
    target.mkdir()
    (target / "__init__.py").write_text("", encoding="utf-8")
    (target / "controller.py").write_text("VALUE = 1\n", encoding="utf-8")
    output = tmp_path / "report.json"

    exit_code = main(
        [
            "--source",
            str(_CASE / "reference"),
            "--target",
            str(target),
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )
    capsys.readouterr()
    rows = _rule_rows(json.loads(output.read_text(encoding="utf-8")))

    assert exit_code == 0
    assert rows
    assert {row["status"] for row in rows} == {"SKIPPED"}


def _statuses(rows: list[dict]) -> dict[str, str]:
    return {row["rule_id"]: row["status"] for row in rows}


def test_with_dynamic_a_call_past_the_service_fails_only_the_forbid_rule(
    tmp_path: Path, capsys
) -> None:
    exit_code, rows = _run("target_fail_bypass_service", tmp_path, "--dynamic")
    capsys.readouterr()

    assert exit_code == 1
    assert _statuses(rows) == {
        "DYN001/forbid_runtime_calls/v1": "FAILED",
        "DYN001/require_runtime_calls/v1": "OK",
    }
    failed = next(row for row in rows if row["status"] == "FAILED")
    assert "handle_order calls repository:OrderRepository.get" in failed["message"]


def test_with_dynamic_skipping_the_service_fails_only_the_require_rule(
    tmp_path: Path, capsys
) -> None:
    exit_code, rows = _run("target_fail_logic_in_controller", tmp_path, "--dynamic")
    capsys.readouterr()

    assert exit_code == 1
    assert _statuses(rows) == {
        "DYN001/forbid_runtime_calls/v1": "OK",
        "DYN001/require_runtime_calls/v1": "FAILED",
    }
    failed = next(row for row in rows if row["status"] == "FAILED")
    assert "case 0: no direct call into service" in failed["message"]


@pytest.mark.parametrize(
    ("target", "fragment"),
    [
        ("target_fail_direct_balance", "bank:transfer sets Account.balance"),
        ("target_fail_helper_write", "bank:_move sets Account.balance"),
    ],
)
def test_with_dynamic_a_foreign_write_fails_the_encapsulation_rule(
    target: str, fragment: str, tmp_path: Path, capsys
) -> None:
    exit_code, rows = _run(
        target, tmp_path, "--dynamic", case=_SHOWCASE / "dyn003_encapsulation"
    )
    capsys.readouterr()

    assert exit_code == 1
    assert _statuses(rows) == {"DYN003/forbid_foreign_writes/v1": "FAILED"}
    assert fragment in rows[0]["message"]


def test_with_dynamic_an_encapsulated_target_passes(tmp_path: Path, capsys) -> None:
    exit_code, rows = _run(
        "target_pass_other_order",
        tmp_path,
        "--dynamic",
        case=_SHOWCASE / "dyn003_encapsulation",
    )
    capsys.readouterr()

    assert exit_code == 0
    assert _statuses(rows) == {"DYN003/forbid_foreign_writes/v1": "OK"}


@pytest.mark.parametrize(
    ("target", "fragment"),
    [
        ("target_pass_other_results", None),
        (
            "target_fail_notifier_reads_repository",
            "case 0: notifier -> repository is not in the reference",
        ),
        (
            "target_fail_skips_notifier",
            "case 0: the reference's service -> notifier never happened",
        ),
    ],
)
def test_with_dynamic_module_calls_are_compared_with_the_reference(
    target: str, fragment: str | None, tmp_path: Path, capsys
) -> None:
    exit_code, rows = _run(
        target, tmp_path, "--dynamic", case=_SHOWCASE / "dyn001_reference_calls"
    )
    capsys.readouterr()

    rule_id = "DYN001/enforce_reference_calls/v1"
    if fragment is None:
        assert exit_code == 0
        assert _statuses(rows) == {rule_id: "OK"}
    else:
        assert exit_code == 1
        assert _statuses(rows) == {rule_id: "FAILED"}
        assert fragment in rows[0]["message"]


@pytest.mark.parametrize(
    ("target", "fragment"),
    [
        ("target_pass_other_internals", None),
        (
            "target_fail_builds_in_init",
            "service:OrderService.__init__ creates repository:OrderRepository",
        ),
        (
            "target_fail_builds_in_method",
            "service:OrderService.place creates repository:OrderRepository",
        ),
    ],
)
def test_with_dynamic_a_dependency_built_in_place_fails_the_injection_rule(
    target: str, fragment: str | None, tmp_path: Path, capsys
) -> None:
    exit_code, rows = _run(
        target, tmp_path, "--dynamic", case=_SHOWCASE / "dyn004_injection"
    )
    capsys.readouterr()

    rule_id = "DYN004/forbid_runtime_instantiation/v1"
    if fragment is None:
        assert exit_code == 0
        assert _statuses(rows) == {rule_id: "OK"}
    else:
        assert exit_code == 1
        assert _statuses(rows) == {rule_id: "FAILED"}
        assert fragment in rows[0]["message"]


def test_with_dynamic_a_correct_target_passes_every_case(
    tmp_path: Path, capsys
) -> None:
    exit_code, rows = _run("target_pass_basic", tmp_path, "--dynamic")
    capsys.readouterr()

    assert exit_code == 0
    assert {row["status"] for row in rows} == {"OK"}


_REQUIRE_MEMBERS = "DYN005/require_runtime_members/v1"
_FORBID_MEMBERS = "DYN005/forbid_runtime_members/v1"


@pytest.mark.parametrize(
    ("target", "failed", "fragment"),
    [
        ("target_pass_explicit", None, None),
        ("target_pass_mixin", None, None),
        ("target_fail_missing_port", _REQUIRE_MEMBERS, "case 0: the instance has no"),
        (
            "target_fail_stores_password",
            _FORBID_MEMBERS,
            "case 0: the instance has 'password' (from instance)",
        ),
    ],
)
def test_with_dynamic_instance_members_are_checked_however_they_are_set(
    target: str, failed: str | None, fragment: str | None, tmp_path: Path, capsys
) -> None:
    exit_code, rows = _run(
        target, tmp_path, "--dynamic", case=_SHOWCASE / "dyn005_runtime_members"
    )
    capsys.readouterr()

    expected = {_REQUIRE_MEMBERS: "OK", _FORBID_MEMBERS: "OK"}
    if failed is not None:
        expected[failed] = "FAILED"
    assert exit_code == (0 if failed is None else 1)
    assert _statuses(rows) == expected
    if fragment is not None:
        row = next(row for row in rows if row["rule_id"] == failed)
        assert fragment in row["message"]


_CONCRETE = "DYN006/is_runtime_concrete_class/v1"
_ABSTRACT = "DYN006/is_runtime_abstract_class/v1"
_PROTOCOL = "DYN007/implements_runtime_protocol/v1"


@pytest.mark.parametrize(
    ("target", "failed", "fragment"),
    [
        ("target_pass_basic", None, None),
        ("target_pass_runtime_wiring", None, None),
        (
            "target_fail_missing_len",
            _CONCRETE,
            "the class is abstract at run time; unimplemented: __len__",
        ),
        ("target_fail_concrete_storage", _ABSTRACT, "the class is concrete"),
        (
            "target_fail_export_arity",
            _PROTOCOL,
            "'export' does not accept 1 positional argument(s)",
        ),
    ],
)
def test_with_dynamic_class_shape_is_decided_by_python(
    target: str, failed: str | None, fragment: str | None, tmp_path: Path, capsys
) -> None:
    exit_code, rows = _run(
        target, tmp_path, "--dynamic", case=_SHOWCASE / "dyn006_runtime_classes"
    )
    capsys.readouterr()

    expected = {_CONCRETE: "OK", _ABSTRACT: "OK", _PROTOCOL: "OK"}
    if failed is not None:
        expected[failed] = "FAILED"
    assert exit_code == (0 if failed is None else 1)
    assert _statuses(rows) == expected
    if fragment is not None:
        row = next(row for row in rows if row["rule_id"] == failed)
        assert fragment in row["message"]


_SINGLETON = "DYN008/is_runtime_singleton/v1"
_OBSERVER = "DYN008/enforce_runtime_observer/v1"
_DELEGATION = "DYN008/require_runtime_delegation/v1"


@pytest.mark.parametrize(
    ("target", "failed", "fragment"),
    [
        ("target_pass_basic", None, None),
        ("target_pass_other_implementations", None, None),
        (
            "target_fail_new_instance_each_time",
            _SINGLETON,
            "two accesses via instance returned different objects",
        ),
        (
            "target_fail_unsubscribe_ignored",
            _OBSERVER,
            "the listener was still called after unsubscribe()",
        ),
        (
            "target_fail_hardcoded_discount",
            _DELEGATION,
            "never delegated to strategy.apply()",
        ),
    ],
)
def test_with_dynamic_design_patterns_are_judged_by_behaviour(
    target: str, failed: str | None, fragment: str | None, tmp_path: Path, capsys
) -> None:
    exit_code, rows = _run(
        target, tmp_path, "--dynamic", case=_SHOWCASE / "dyn008_patterns"
    )
    capsys.readouterr()

    expected = {_SINGLETON: "OK", _OBSERVER: "OK", _DELEGATION: "OK"}
    if failed is not None:
        expected[failed] = "FAILED"
    assert exit_code == (0 if failed is None else 1)
    assert _statuses(rows) == expected
    if fragment is not None:
        row = next(row for row in rows if row["rule_id"] == failed)
        assert fragment in row["message"]


def test_without_dynamic_the_pattern_rules_are_skipped(tmp_path: Path, capsys) -> None:
    exit_code, rows = _run(
        "target_fail_hardcoded_discount",
        tmp_path,
        case=_SHOWCASE / "dyn008_patterns",
    )
    capsys.readouterr()

    assert exit_code == 0
    assert set(_statuses(rows)) == {_SINGLETON, _OBSERVER, _DELEGATION}
    assert {row["status"] for row in rows} == {"SKIPPED"}


def test_an_unavailable_sandbox_stops_the_run_before_any_target_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from pythonarchtesting.dynamic import sandbox

    def unavailable(policy: object) -> None:
        raise sandbox.SandboxUnavailableError("user namespaces are disabled")

    monkeypatch.setattr(sandbox, "check_available", unavailable)

    with pytest.raises(SystemExit) as exc_info:
        _run("target_pass_basic", tmp_path, "--dynamic", "--sandbox", "bwrap")

    assert exc_info.value.code == 2
    assert "user namespaces are disabled" in capsys.readouterr().err


def test_a_non_positive_memory_limit_is_a_usage_error(tmp_path: Path, capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _run("target_pass_basic", tmp_path, "--dynamic", "--sandbox-memory-mb", "0")

    assert exc_info.value.code == 2
    capsys.readouterr()


@pytest.mark.parametrize(
    "flags",
    [("--sandbox", "none"), ("--sandbox", "bwrap"), ("--sandbox-memory-mb", "64")],
)
def test_sandbox_flags_without_dynamic_are_a_usage_error(
    tmp_path: Path, capsys, flags: tuple[str, str]
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _run("target_pass_basic", tmp_path, *flags)

    assert exc_info.value.code == 2
    assert "apply only with --dynamic" in capsys.readouterr().err


def test_default_sandbox_flags_without_dynamic_are_accepted(
    tmp_path: Path, capsys
) -> None:
    exit_code, rows = _run("target_pass_basic", tmp_path, "--sandbox", "limits")
    capsys.readouterr()

    assert exit_code == 0
    assert {row["status"] for row in rows} == {"SKIPPED"}


def test_dynamic_with_validate_declarations_is_a_usage_error(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--source",
                str(_CASE / "reference"),
                "--format",
                "json",
                "--validate-declarations",
                "--dynamic",
            ]
        )

    assert exc_info.value.code == 2
    assert "drop --dynamic" in capsys.readouterr().err


def test_without_dynamic_skipped_runtime_rules_are_warned_about(
    tmp_path: Path, capsys
) -> None:
    exit_code, rows = _run("target_pass_basic", tmp_path)
    err = capsys.readouterr().err

    assert exit_code == 0
    assert {row["status"] for row in rows} == {"SKIPPED"}
    warnings = [line for line in err.splitlines() if line.startswith("warning:")]
    assert len(warnings) == 1
    assert "--dynamic" in warnings[0]


def test_with_dynamic_no_skip_warning_is_printed(tmp_path: Path, capsys) -> None:
    _run("target_pass_basic", tmp_path, "--dynamic")

    assert "warning:" not in capsys.readouterr().err


def test_a_pass_with_unchecked_code_is_flagged_and_counted(
    tmp_path: Path, capsys
) -> None:
    # The reordered transfer leaves lines no case runs (see the showcase).
    exit_code, rows = _run(
        "target_pass_other_order",
        tmp_path,
        "--dynamic",
        case=_SHOWCASE / "dyn003_encapsulation",
    )
    err = capsys.readouterr().err

    assert exit_code == 0
    assert [row["details"]["unverified"] for row in rows] == [["unexercised_lines"]]
    warnings = [line for line in err.splitlines() if line.startswith("warning:")]
    assert warnings == [
        "warning: 1 runtime rule result(s) passed with code or cases left "
        "unchecked; see details.unverified"
    ]
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["results"]["unverified_total"] == 1


def test_the_markdown_report_counts_passes_with_unchecked_code(
    tmp_path: Path, capsys
) -> None:
    case = _SHOWCASE / "dyn003_encapsulation"
    main(
        [
            "--source",
            str(case / "reference"),
            "--target",
            str(case / "assignments" / "target_pass_other_order"),
            "--format",
            "markdown",
            "--output",
            str(tmp_path / "md"),
            "--dynamic",
        ]
    )
    capsys.readouterr()

    pages = "\n".join(
        path.read_text(encoding="utf-8") for path in (tmp_path / "md").rglob("*.md")
    )
    assert "- Passed With Unchecked Code: 1 (see `details.unverified`)" in pages


_BROKEN_CASE = """
from typing import Annotated, Any

from pythonarchtesting.rules import forbid_runtime_calls


class Store:
    def save(self, value: Any) -> None:
        self.value = value


def handle(store: Any) -> None:
    __archtest__: Annotated[  # noqa: F842
        None,
        forbid_runtime_calls(
            "json", cases=[{"args": [{"$new": "{class_name}"}]}]
        ),
    ]
    store.save(1)
"""


_TARGET = """
from typing import Any


class Repository:
    def save(self, value: Any) -> None:
        self.value = value


def handle(store: Any) -> None:
    store.save(1)
"""


@pytest.mark.parametrize(
    ("class_name", "status", "reason"),
    [
        ("Missing", "ERROR", "reference_case_invalid"),
        ("Store", "FAILED", "case_setup_failed"),
    ],
)
def test_a_case_that_cannot_run_is_blamed_on_whoever_it_fails_for(
    tmp_path: Path, class_name: str, status: str, reason: str
) -> None:
    reference = tmp_path / "reference"
    target = tmp_path / "target"
    reference.mkdir()
    target.mkdir()
    (reference / "app.py").write_text(
        _BROKEN_CASE.replace("{class_name}", class_name), encoding="utf-8"
    )
    # The target names the class differently, so "Store" exists only in the
    # reference: the case is right, and only the target cannot run it.
    (target / "app.py").write_text(_TARGET, encoding="utf-8")
    output = tmp_path / "report.json"

    main(
        [
            "--source",
            str(reference),
            "--target",
            str(target),
            "--format",
            "json",
            "--output",
            str(output),
            "--dynamic",
        ]
    )
    rows = _rule_rows(json.loads(output.read_text(encoding="utf-8")))

    assert [(row["status"], row["details"]["reason"]) for row in rows] == [
        (status, reason)
    ]


def test_markdown_locations_point_into_the_target(tmp_path: Path) -> None:
    case = _SHOWCASE / "dyn003_encapsulation"
    output = tmp_path / "md"

    main(
        [
            "--source",
            str(case / "reference"),
            "--target",
            str(case / "assignments" / "target_fail_direct_balance"),
            "--format",
            "markdown",
            "--output",
            str(output),
            "--dynamic",
        ]
    )
    rows = [
        line
        for line in (output / "targets" / "target_fail_direct_balance.md")
        .read_text(encoding="utf-8")
        .splitlines()
        if "DYN003/forbid_foreign_writes" in line
    ]

    # transfer is on line 8 of the target, line 22 of the reference.
    assert len(rows) == 1
    assert "| bank.py:8 |" in rows[0]
