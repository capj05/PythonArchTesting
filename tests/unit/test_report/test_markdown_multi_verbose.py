from __future__ import annotations

from pathlib import Path

from pythonarchtesting.report.ir.normalize import report_dict_to_ir
from pythonarchtesting.report.markdown_generator import MarkdownReportGenerator


def _target_payload(
    *,
    target_id: str,
    display_name: str,
    target_path: str,
    exit_code: int,
    results: list[dict],
    matches: list[dict],
    top_rules: list[dict] | None = None,
) -> dict:
    status_counts: dict[str, int] = {}
    severity_counts: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        severity = str(result["severity"])
        status_counts[status] = status_counts.get(status, 0) + 1
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
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
            "top_rules": top_rules or [],
            "top_source_files": [],
        },
        "matching": {
            "matches": matches,
            "matching_config": {},
        },
        "results": results,
    }


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


def _verbose_report() -> dict:
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
            fix_hints=["Remove forbidden import"],
        )
    ]
    beta_results = [
        _result(
            project_id="beta",
            result_id="beta-warn-1",
            rule_id="arch/rule-b",
            status="WARNING",
            severity="warning",
            message="Beta uses a discouraged dependency",
            source_name="Warnings.check",
            line=20,
            fix_hints=["Review dependency usage"],
        )
    ]
    gamma_results = [
        _result(
            project_id="gamma",
            result_id="gamma-fail-1",
            rule_id="arch/rule-c",
            status="FAILED",
            severity="error",
            message="Gamma layering failed",
            source_name="Controller.handle",
            line=30,
            fix_hints=["Split controller and repository concerns"],
            evidence=[
                {
                    "type": "dependency_path",
                    "payload": {"value": "SECRET-EVIDENCE"},
                    "location": {"file": "gamma.py", "line": 30},
                }
            ],
        ),
        _result(
            project_id="gamma",
            result_id="gamma-skip-1",
            rule_id="arch/rule-c",
            status="SKIPPED",
            severity="warning",
            message="Gamma target could not be matched",
            source_name="Controller.handle",
            line=31,
            target_name="unresolved target",
            match_status="unmatched",
            fix_hints=["Verify target naming before rerunning"],
        ),
    ]
    delta_results = [
        _result(
            project_id="delta",
            result_id="delta-fail-1",
            rule_id="arch/rule-d",
            status="FAILED",
            severity="error",
            message="Delta still has one forbidden dependency",
            source_name="Service.run",
            line=40,
            fix_hints=["Remove the last forbidden dependency"],
        ),
        _result(
            project_id="delta",
            result_id="delta-ok-1",
            rule_id="arch/rule-pass",
            status="OK",
            severity="info",
            message="Delta rule pass 1",
            source_name="Pass.one",
            line=41,
        ),
        _result(
            project_id="delta",
            result_id="delta-ok-2",
            rule_id="arch/rule-pass",
            status="OK",
            severity="info",
            message="Delta rule pass 2",
            source_name="Pass.two",
            line=42,
        ),
        _result(
            project_id="delta",
            result_id="delta-ok-3",
            rule_id="arch/rule-pass-two",
            status="OK",
            severity="info",
            message="Delta rule pass 3",
            source_name="Pass.three",
            line=43,
        ),
        _result(
            project_id="delta",
            result_id="delta-ok-4",
            rule_id="arch/rule-pass-three",
            status="OK",
            severity="info",
            message="Delta rule pass 4",
            source_name="Pass.four",
            line=44,
        ),
    ]
    epsilon_results = [
        _result(
            project_id="epsilon",
            result_id="epsilon-ok-1",
            rule_id="arch/rule-e",
            status="OK",
            severity="info",
            message="Epsilon rule pass 1",
            source_name="All.good",
            line=50,
        ),
        _result(
            project_id="epsilon",
            result_id="epsilon-ok-2",
            rule_id="arch/rule-f",
            status="OK",
            severity="info",
            message="Epsilon rule pass 2",
            source_name="All.goodAgain",
            line=51,
        ),
    ]
    return {
        "schema_version": "2",
        "framework_version": "test",
        "generated_at": "2026-04-12T00:00:00Z",
        "exit_code": 1,
        "run": {"source_path": "/src"},
        "summary": {
            "targets_total": 5,
            "targets_failed": 3,
            "targets_passed": 2,
            "results": {
                "results_total": 11,
                "status_counts": {
                    "FAILED": 3,
                    "WARNING": 1,
                    "SKIPPED": 1,
                    "OK": 6,
                },
                "severity_counts": {
                    "error": 3,
                    "warning": 2,
                    "info": 6,
                },
                "category_counts": {"arch": 11},
                "top_rules": [
                    {"name": "arch/rule-c", "count": 2},
                    {"name": "arch/rule-a", "count": 1},
                    {"name": "arch/rule-d", "count": 1},
                ],
                "top_source_files": [],
            },
        },
        "targets": [
            _target_payload(
                target_id="alpha",
                display_name="Alpha",
                target_path="/targets/alpha",
                exit_code=1,
                results=alpha_results,
                matches=[
                    {
                        "source_entity_id": "alpha-orphan",
                        "status": "low_confidence",
                        "target_entity_id": "alpha-target",
                        "confidence": 0.49,
                        "candidates": [],
                    }
                ],
                top_rules=[{"name": "arch/rule-a", "count": 1}],
            ),
            _target_payload(
                target_id="gamma",
                display_name="Gamma",
                target_path="/targets/gamma",
                exit_code=1,
                results=gamma_results,
                matches=[
                    {
                        "source_entity_id": "gamma-unmatched",
                        "status": "unmatched",
                        "target_entity_id": None,
                        "confidence": 0.0,
                        "candidates": [],
                    }
                ],
                top_rules=[{"name": "arch/rule-c", "count": 2}],
            ),
            _target_payload(
                target_id="delta",
                display_name="Delta",
                target_path="/targets/delta",
                exit_code=1,
                results=delta_results,
                matches=[],
                top_rules=[{"name": "arch/rule-d", "count": 1}],
            ),
            _target_payload(
                target_id="beta",
                display_name="Beta",
                target_path="/targets/beta",
                exit_code=0,
                results=beta_results,
                matches=[],
                top_rules=[{"name": "arch/rule-b", "count": 1}],
            ),
            _target_payload(
                target_id="epsilon",
                display_name="Epsilon",
                target_path="/targets/epsilon",
                exit_code=0,
                results=epsilon_results,
                matches=[],
                top_rules=[{"name": "arch/rule-e", "count": 1}],
            ),
        ],
    }


def _render_verbose_bundle(tmp_path: Path) -> Path:
    document = report_dict_to_ir(_verbose_report(), kind="multi")
    output_root = tmp_path / "verbose_bundle"
    index_path = MarkdownReportGenerator(document, markdown_mode="verbose").generate(
        output_file=str(output_root)
    )
    return Path(index_path)


def _page(root: Path, name: str) -> str:
    return (root / "targets" / f"{name}.md").read_text(encoding="utf-8")


def _assert_section_order(text: str, sections: list[str]) -> None:
    positions = [text.index(section) for section in sections]
    assert positions == sorted(positions)


def test_verbose_multi_target_pages_follow_remediation_first_structure(
    tmp_path: Path,
) -> None:
    index_path = _render_verbose_bundle(tmp_path)
    root = index_path.parent

    alpha_md = _page(root, "alpha")
    beta_md = _page(root, "beta")
    gamma_md = _page(root, "gamma")
    delta_md = _page(root, "delta")
    epsilon_md = _page(root, "epsilon")

    _assert_section_order(
        alpha_md,
        [
            "## Verdict",
            "## Issue Summary by Rule",
            "## Rule Details",
            "## Compact Passed Summary",
        ],
    )
    assert "## Warnings" not in alpha_md
    assert "## Metadata" not in alpha_md
    assert "## Matching" not in alpha_md
    assert "## Results" not in alpha_md
    assert "Matching Candidates (Debug)" not in alpha_md
    assert "matching summary explains uncertainty (low confidence: 1)." in alpha_md
    assert "**Matching note:**" not in alpha_md

    _assert_section_order(
        beta_md,
        [
            "## Verdict",
            "## Issue Summary by Rule",
            "## Rule Details",
            "## Warnings",
            "## Compact Passed Summary",
        ],
    )
    assert "No failing rules." in beta_md
    assert "No failing rule details." in beta_md
    assert "### arch/rule-b" in beta_md
    assert "Review dependency usage" in beta_md

    _assert_section_order(
        gamma_md,
        [
            "## Verdict",
            "## Issue Summary by Rule",
            "## Rule Details",
            "## Compact Passed Summary",
        ],
    )
    assert (
        "**Matching note:** Matching context: skipped results: 1, unmatched: 1."
        in gamma_md
    )
    assert "**Evidence summary:** Evidence available for 1 result(s)." in gamma_md
    assert "SECRET-EVIDENCE" not in gamma_md

    assert "delta-ok-1" not in delta_md
    assert "- Passed checks: 4" in delta_md
    assert (
        "- Top passed rules: arch/rule-pass, arch/rule-pass-three, "
        "arch/rule-pass-two" in delta_md
    )

    _assert_section_order(
        epsilon_md,
        [
            "## Verdict",
            "## Issue Summary by Rule",
            "## Rule Details",
            "## Compact Passed Summary",
        ],
    )
    assert "No failing rules." in epsilon_md
    assert "- Passed checks: 2" in epsilon_md


def test_verbose_multi_target_run_index_groups_targets_and_links_pages(
    tmp_path: Path,
) -> None:
    index_path = _render_verbose_bundle(tmp_path)
    index_md = index_path.read_text(encoding="utf-8")

    _assert_section_order(
        index_md,
        [
            "## At a glance",
            "## Projects with issues",
            "## Common failure causes",
            "## Projects with warnings only",
            "<summary><strong>Passed projects (1)</strong></summary>",
            "## Run metadata",
        ],
    )
    assert "## Verdict" not in index_md
    assert "## Targets With Issues" not in index_md
    assert "## Warnings Only" not in index_md
    assert "## OK Targets" not in index_md
    assert "## Rule Hotspots" not in index_md
    assert (
        "| [Alpha](targets/alpha.md) | ISSUES | 1 | 1 | Alpha import is forbidden |"
        in index_md
    )
    assert (
        "| [Gamma](targets/gamma.md) | ISSUES | 1 | 1 | Gamma layering failed |"
        in index_md
    )
    assert (
        "| [Delta](targets/delta.md) | ISSUES | 1 | 1 | Delta still has one forbidden dependency |"
        in index_md
    )
    assert (
        "| [Beta](targets/beta.md) | 1 | Beta uses a discouraged dependency |"
        in index_md
    )
    assert "| [Epsilon](targets/epsilon.md) | 2 |" in index_md
    assert "| `arch/rule-c` | 1 | 2 |" in index_md
    assert "| Target | Path | Exit | Results | Failed |" not in index_md
    assert "## Matching Debug" not in index_md
    assert "## Raw Evidence" not in index_md
    assert "## Full Result Table" not in index_md


def test_standard_mode_writes_compact_run_index_without_target_pages(
    tmp_path: Path,
) -> None:
    document = report_dict_to_ir(_verbose_report(), kind="multi")
    output_root = tmp_path / "standard_bundle"

    index_path = MarkdownReportGenerator(document, markdown_mode="standard").generate(
        output_file=str(output_root)
    )

    assert index_path == str(output_root / "report.md")
    assert (output_root / "report.md").is_file()
    assert not (output_root / "targets").exists()
