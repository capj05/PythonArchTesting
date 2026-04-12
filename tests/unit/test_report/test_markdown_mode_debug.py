from __future__ import annotations

from pathlib import Path

from pythonarchtesting.report.ir.normalize import report_dict_to_ir
from pythonarchtesting.report.markdown_generator import MarkdownReportGenerator


def _counts(results: list[dict]) -> tuple[dict[str, int], dict[str, int]]:
    status_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        severity = str(result["severity"])
        status_counts[status] = status_counts.get(status, 0) + 1
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
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
    matches: list[dict],
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
            "top_rules": [{"name": "arch/rule-a", "count": 2}],
            "top_source_files": [{"name": f"{target_id}.py", "count": len(results)}],
            "timings": {"evaluation_seconds": 0.12},
        },
        "matching": {
            "matches": matches,
            "matching_config": {"strategy": "name-first"},
        },
        "results": results,
        "artifacts": [{"kind": "log", "path": f"artifacts/{target_id}.log"}],
    }


def _single_report() -> dict:
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
            evidence=[
                {
                    "type": "dependency_path",
                    "payload": {"value": "SECRET-EVIDENCE"},
                    "location": {"file": "alpha.py", "line": 10},
                }
            ],
        ),
        _result(
            project_id="alpha",
            result_id="alpha-skip-1",
            rule_id="arch/rule-a",
            status="SKIPPED",
            severity="warning",
            message="Alpha target could not be matched",
            source_name="Service.run",
            line=11,
            target_name="unresolved target",
            match_status="unmatched",
            fix_hints=["Verify target naming before rerunning"],
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
    return {
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
            "top_rules": [{"name": "arch/rule-a", "count": 2}],
            "top_source_files": [{"name": "alpha.py", "count": len(results)}],
            "timings": {"evaluation_seconds": 0.12},
        },
        "matching": {
            "matches": [
                {
                    "source_entity_id": "alpha-alpha-fail-1-source",
                    "status": "low_confidence",
                    "target_entity_id": "alpha-alpha-fail-1-target",
                    "confidence": 0.44,
                    "candidates": [
                        {
                            "target_entity_id": "alpha-alpha-fail-1-target",
                            "confidence": 0.44,
                            "breakdown": {"name": 0.7, "ast": 0.3},
                            "explanations": "Closest available target",
                        }
                    ],
                }
            ],
            "matching_config": {"strategy": "name-first"},
        },
        "results": results,
        "artifacts": [{"kind": "log", "path": "artifacts/alpha.log"}],
    }


def _single_matching_context() -> dict:
    return {
        "kind": "single",
        "targets": {
            "__single__": {
                "sources": {
                    "alpha-alpha-fail-1-source": {
                        "id": "alpha-alpha-fail-1-source",
                        "name": "Source Alpha",
                        "type": "method",
                        "location": "alpha.py:10",
                    }
                },
                "targets": {
                    "alpha-alpha-fail-1-target": {
                        "id": "alpha-alpha-fail-1-target",
                        "name": "Target Alpha",
                        "type": "method",
                        "location": "target.py:10",
                    }
                },
            }
        },
    }


def _multi_report() -> dict:
    alpha_results = _single_report()["results"]
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
        )
    ]
    alpha_matches = _single_report()["matching"]["matches"]
    beta_matches: list[dict] = []
    return {
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
                "status_counts": {"FAILED": 1, "SKIPPED": 1, "OK": 2},
                "severity_counts": {"error": 1, "warning": 1, "info": 2},
                "category_counts": {"arch": len(alpha_results) + len(beta_results)},
                "top_rules": [{"name": "arch/rule-a", "count": 2}],
                "top_source_files": [{"name": "alpha.py", "count": len(alpha_results)}],
                "timings": {"evaluation_seconds": 0.24},
            },
        },
        "targets": [
            _target_payload(
                target_id="alpha",
                display_name="Alpha",
                target_path="/targets/alpha",
                exit_code=1,
                results=alpha_results,
                matches=alpha_matches,
            ),
            _target_payload(
                target_id="beta",
                display_name="Beta",
                target_path="/targets/beta",
                exit_code=0,
                results=beta_results,
                matches=beta_matches,
            ),
        ],
    }


def _multi_matching_context() -> dict:
    return {
        "kind": "multi",
        "targets": {
            ("Alpha", "/targets/alpha"): {
                "sources": {
                    "alpha-alpha-fail-1-source": {
                        "id": "alpha-alpha-fail-1-source",
                        "name": "Source Alpha",
                        "type": "method",
                        "location": "alpha.py:10",
                    }
                },
                "targets": {
                    "alpha-alpha-fail-1-target": {
                        "id": "alpha-alpha-fail-1-target",
                        "name": "Target Alpha",
                        "type": "method",
                        "location": "target.py:10",
                    }
                },
            }
        },
    }


def _assert_section_order(text: str, sections: list[str]) -> None:
    positions = [text.index(section) for section in sections]
    assert positions == sorted(positions)


def test_single_target_verbose_mode_hides_debug_sections() -> None:
    document = report_dict_to_ir(_single_report(), kind="single")

    rendered = MarkdownReportGenerator(document, markdown_mode="verbose").generate()

    _assert_section_order(
        rendered,
        [
            "## Verdict",
            "## Issue Summary by Rule",
            "## Rule Details",
            "## Compact Passed Summary",
        ],
    )
    assert "Matching Candidates (Debug)" not in rendered
    assert "## Matching Debug" not in rendered
    assert "## Raw Evidence" not in rendered
    assert "## Full Result Table" not in rendered
    assert "## Internal Diagnostics" not in rendered
    assert "## Results" not in rendered
    assert "SECRET-EVIDENCE" not in rendered
    assert "[Back to run index]" not in rendered
    assert (
        "**Matching note:** Matching context: skipped results: 1, unmatched: 1."
        in rendered
    )


def test_single_target_debug_mode_appends_debug_sections() -> None:
    document = report_dict_to_ir(_single_report(), kind="single")

    rendered = MarkdownReportGenerator(
        document,
        matching_debug_context=_single_matching_context(),
        markdown_mode="debug",
    ).generate()

    _assert_section_order(
        rendered,
        [
            "## Verdict",
            "## Issue Summary by Rule",
            "## Rule Details",
            "## Compact Passed Summary",
            "## Matching Debug",
            "## Raw Evidence",
            "## Full Result Table",
            "## Internal Diagnostics",
        ],
    )
    assert "### Matching Candidates (Debug)" in rendered
    assert "Source Alpha" in rendered
    assert "SECRET-EVIDENCE" in rendered
    assert "alpha-ok-1" in rendered
    assert "### Matching Config" in rendered
    assert "### Timings" in rendered


def test_multi_target_debug_mode_keeps_index_clean_and_appends_target_debug(
    tmp_path: Path,
) -> None:
    document = report_dict_to_ir(_multi_report(), kind="multi")
    output_root = tmp_path / "debug_bundle"

    index_path = MarkdownReportGenerator(
        document,
        matching_debug_context=_multi_matching_context(),
        markdown_mode="debug",
    ).generate(output_file=str(output_root))

    index_md = Path(index_path).read_text(encoding="utf-8")
    alpha_md = (output_root / "targets" / "alpha.md").read_text(encoding="utf-8")

    _assert_section_order(
        alpha_md,
        [
            "## Verdict",
            "## Issue Summary by Rule",
            "## Rule Details",
            "## Compact Passed Summary",
            "## Matching Debug",
            "## Raw Evidence",
            "## Full Result Table",
            "## Internal Diagnostics",
        ],
    )
    assert "Matching Candidates (Debug)" not in index_md
    assert "## Raw Evidence" not in index_md
    assert "SECRET-EVIDENCE" not in index_md
    assert "- Debug appendices: available on target pages." in index_md
    assert "### Matching Candidates (Debug)" in alpha_md
    assert "Source Alpha" in alpha_md
    assert "SECRET-EVIDENCE" in alpha_md
    assert "alpha-ok-1" in alpha_md
