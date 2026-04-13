"""Shared fixtures for markdown mode acceptance tests."""

from __future__ import annotations

import pytest

from pythonarchtesting.report.ir.normalize import report_dict_to_ir


def _counts(results: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    status_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    for result in results:
        status_counts[result["status"]] = status_counts.get(result["status"], 0) + 1
        severity_counts[result["severity"]] = (
            severity_counts.get(result["severity"], 0) + 1
        )
    return status_counts, severity_counts


def _result(
    *,
    project_id: str,
    result_id: str,
    rule_id: str,
    status: str,
    severity: str,
    message: str,
    source_name: str,
    line: int,
    target_name: str = "Target.run",
    match_status: str | None = "matched",
    fix_hints: list[str] | None = None,
    evidence: list[dict] | None = None,
) -> dict:
    return {
        "project_id": project_id,
        "result_id": result_id,
        "category": "arch",
        "rule_id": rule_id,
        "rule_type": rule_id,
        "severity": severity,
        "status": status,
        "message": message,
        "source_entity_id": f"{project_id}-{result_id}-source",
        "target_entity_id": (
            None
            if target_name == "unresolved target"
            else f"{project_id}-{result_id}-target"
        ),
        "match_status": match_status,
        "source": {
            "module": f"pkg.{project_id}",
            "qualname": source_name,
            "file": f"{project_id}.py",
            "line": line,
        },
        "target": (
            {
                "module": "pkg.target",
                "qualname": target_name,
                "file": "target.py",
                "line": line,
            }
            if target_name != "unresolved target"
            else {}
        ),
        "evidence": evidence or [],
        "details": {},
        "fix_hints": fix_hints or [],
    }


def _target_payload(
    *,
    target_id: str,
    display_name: str,
    target_path: str,
    exit_code: int,
    results: list[dict],
) -> dict:
    status_counts, severity_counts = _counts(results)
    return {
        "target_id": target_id,
        "display_name": display_name,
        "target_path": target_path,
        "exit_code": exit_code,
        "summary": {
            "results_total": len(results),
            "status_counts": status_counts,
            "severity_counts": severity_counts,
            "category_counts": {"arch": len(results)} if results else {},
        },
        "matching": {"matches": []},
        "results": results,
    }


@pytest.fixture()
def single_doc():
    """A single-target IR document with one FAILED result."""
    results = [
        _result(
            project_id="alpha",
            result_id="alpha-fail-1",
            rule_id="arch/rule-a",
            status="FAILED",
            severity="error",
            message="Alpha import is forbidden",
            source_name="Service.run",
            line=10,
            fix_hints=["Remove forbidden import"],
        ),
        _result(
            project_id="alpha",
            result_id="alpha-ok-1",
            rule_id="arch/rule-pass",
            status="OK",
            severity="info",
            message="Alpha rule pass",
            source_name="Service.ok",
            line=12,
        ),
    ]
    status_counts, severity_counts = _counts(results)
    report_dict = {
        "schema_version": "2",
        "framework_version": "test",
        "generated_at": "2026-04-12T00:00:00Z",
        "exit_code": 1,
        "run": {"target_path": "/targets/alpha"},
        "summary": {
            "results_total": len(results),
            "status_counts": status_counts,
            "severity_counts": severity_counts,
            "category_counts": {"arch": len(results)},
        },
        "matching": {"matches": []},
        "results": results,
    }
    return report_dict_to_ir(report_dict, kind="single")


@pytest.fixture()
def multi_doc():
    """A multi-target IR document with alpha (failing) and beta (passing) targets."""
    alpha_results = [
        _result(
            project_id="alpha",
            result_id="alpha-fail-1",
            rule_id="arch/rule-a",
            status="FAILED",
            severity="error",
            message="Alpha import is forbidden",
            source_name="Service.run",
            line=10,
        ),
    ]
    beta_results = [
        _result(
            project_id="beta",
            result_id="beta-ok-1",
            rule_id="arch/rule-b",
            status="OK",
            severity="info",
            message="Beta rule pass",
            source_name="All.good",
            line=20,
        ),
    ]
    run_status_counts, run_severity_counts = _counts(alpha_results + beta_results)
    report_dict = {
        "schema_version": "2",
        "framework_version": "test",
        "generated_at": "2026-04-12T00:00:00Z",
        "exit_code": 1,
        "run": {"source_path": "/src"},
        "summary": {
            "targets_total": 2,
            "targets_failed": 1,
            "targets_passed": 1,
            "results": {
                "results_total": len(alpha_results) + len(beta_results),
                "status_counts": run_status_counts,
                "severity_counts": run_severity_counts,
                "category_counts": {"arch": len(alpha_results) + len(beta_results)},
            },
        },
        "targets": [
            _target_payload(
                target_id="alpha",
                display_name="Alpha",
                target_path="/targets/alpha",
                exit_code=1,
                results=alpha_results,
            ),
            _target_payload(
                target_id="beta",
                display_name="Beta",
                target_path="/targets/beta",
                exit_code=0,
                results=beta_results,
            ),
        ],
    }
    return report_dict_to_ir(report_dict, kind="multi")
