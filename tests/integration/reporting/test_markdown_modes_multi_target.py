"""Acceptance tests for multi-target markdown bundle mode rendering."""

from __future__ import annotations

from pathlib import Path

from pythonarchtesting.report.ir.normalize import report_dict_to_ir
from pythonarchtesting.report.markdown_generator import MarkdownReportGenerator


def _assert_section_order(text: str, sections: list[str]) -> None:
    positions = [text.index(section) for section in sections]
    assert positions == sorted(positions)


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
    line: int,
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
        "target_entity_id": f"{project_id}-{result_id}-target",
        "match_status": "matched",
        "source": {
            "module": f"pkg.{project_id}",
            "qualname": "Service.run",
            "file": f"{project_id}.py",
            "line": line,
        },
        "target": {
            "module": "pkg.target",
            "qualname": "Target.run",
            "file": "target.py",
            "line": line,
        },
        "evidence": [],
        "details": {},
        "fix_hints": [],
    }


def _target_payload(
    *,
    target_id: str,
    display_name: str,
    target_path: str,
    exit_code: int,
    results: list[dict],
    top_rules: list[dict] | None = None,
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
            "top_rules": top_rules or [],
            "top_source_files": [],
        },
        "matching": {"matches": [], "matching_config": {}},
        "results": results,
    }


def _triage_doc():
    alpha_results = [
        _result(
            project_id="alpha",
            result_id="alpha-error",
            rule_id="arch/shared-rule",
            status="ERROR",
            severity="error",
            message="Alpha renderer crashed",
            line=10,
        )
    ]
    beta_results = [
        _result(
            project_id="beta",
            result_id="beta-fail",
            rule_id="arch/shared-rule",
            status="FAILED",
            severity="error",
            message="Beta import is forbidden",
            line=20,
        )
    ]
    gamma_results = [
        _result(
            project_id="gamma",
            result_id="gamma-warn",
            rule_id="arch/warn-rule",
            status="WARNING",
            severity="warning",
            message="Gamma dependency is discouraged",
            line=30,
        )
    ]
    delta_results = [
        _result(
            project_id="delta",
            result_id="delta-ok-1",
            rule_id="arch/shared-rule",
            status="OK",
            severity="info",
            message="Delta shared rule passed",
            line=40,
        ),
        _result(
            project_id="delta",
            result_id="delta-ok-2",
            rule_id="arch/pass-only",
            status="OK",
            severity="info",
            message="Delta pass-only rule passed",
            line=41,
        ),
    ]
    all_results = alpha_results + beta_results + gamma_results + delta_results
    run_status_counts, run_severity_counts = _counts(all_results)
    document = {
        "schema_version": "2",
        "framework_version": "test",
        "generated_at": "2026-04-12T00:00:00Z",
        "exit_code": 1,
        "run": {
            "source_path": "/src",
            "config_snapshot": {
                "report": {
                    "multi_target_exit_policy": "any_fail",
                }
            },
        },
        "summary": {
            "targets_total": 4,
            "targets_failed": 2,
            "targets_passed": 2,
            "results": {
                "results_total": len(all_results),
                "status_counts": run_status_counts,
                "severity_counts": run_severity_counts,
                "category_counts": {"arch": len(all_results)},
                "top_rules": [
                    {"name": "arch/shared-rule", "count": 3},
                    {"name": "arch/warn-rule", "count": 1},
                    {"name": "arch/pass-only", "count": 1},
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
                top_rules=[{"name": "arch/shared-rule", "count": 1}],
            ),
            _target_payload(
                target_id="beta",
                display_name="Beta",
                target_path="/targets/beta",
                exit_code=1,
                results=beta_results,
                top_rules=[{"name": "arch/shared-rule", "count": 1}],
            ),
            _target_payload(
                target_id="gamma",
                display_name="Gamma",
                target_path="/targets/gamma",
                exit_code=0,
                results=gamma_results,
                top_rules=[{"name": "arch/warn-rule", "count": 1}],
            ),
            _target_payload(
                target_id="delta",
                display_name="Delta",
                target_path="/targets/delta",
                exit_code=0,
                results=delta_results,
                top_rules=[
                    {"name": "arch/shared-rule", "count": 1},
                    {"name": "arch/pass-only", "count": 1},
                ],
            ),
        ],
    }
    return report_dict_to_ir(document, kind="multi")


def _warnings_and_passes_doc():
    alpha_results = [
        _result(
            project_id="alpha",
            result_id="alpha-warn",
            rule_id="arch/warn-rule",
            status="WARNING",
            severity="warning",
            message="Alpha warning only",
            line=10,
        )
    ]
    beta_results = [
        _result(
            project_id="beta",
            result_id="beta-ok",
            rule_id="arch/pass-only",
            status="OK",
            severity="info",
            message="Beta passed",
            line=20,
        )
    ]
    all_results = alpha_results + beta_results
    run_status_counts, run_severity_counts = _counts(all_results)
    document = {
        "schema_version": "2",
        "framework_version": "test",
        "generated_at": "2026-04-12T00:00:00Z",
        "exit_code": 0,
        "run": {"source_path": "/src"},
        "summary": {
            "targets_total": 2,
            "targets_failed": 0,
            "targets_passed": 2,
            "results": {
                "results_total": len(all_results),
                "status_counts": run_status_counts,
                "severity_counts": run_severity_counts,
                "category_counts": {"arch": len(all_results)},
                "top_rules": [{"name": "arch/warn-rule", "count": 1}],
                "top_source_files": [],
            },
        },
        "targets": [
            _target_payload(
                target_id="alpha",
                display_name="Alpha",
                target_path="/targets/alpha",
                exit_code=0,
                results=alpha_results,
                top_rules=[{"name": "arch/warn-rule", "count": 1}],
            ),
            _target_payload(
                target_id="beta",
                display_name="Beta",
                target_path="/targets/beta",
                exit_code=0,
                results=beta_results,
                top_rules=[{"name": "arch/pass-only", "count": 1}],
            ),
        ],
    }
    return report_dict_to_ir(document, kind="multi")


def test_standard_writes_only_report_index(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    index_path = MarkdownReportGenerator(multi_doc).generate(output_file=str(out))

    assert Path(index_path).name == "report.md"
    assert (out / "report.md").is_file()
    assert not (out / "targets").exists()


def test_standard_run_index_has_required_sections(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc).generate(output_file=str(out))

    index_content = (out / "report.md").read_text(encoding="utf-8")
    assert "> **Verdict:** ISSUES" in index_content
    assert "## At a glance" in index_content
    assert "## Projects with issues" in index_content
    assert "## Common failure causes" in index_content
    assert "## Projects with warnings only" in index_content
    assert "<summary><strong>Passed projects (1)</strong></summary>" in index_content
    assert "## Run metadata" in index_content
    assert "## Verdict" not in index_content
    assert "## Targets With Issues" not in index_content
    assert "## OK Targets" not in index_content
    assert "## Summary" not in index_content
    assert "| Alpha | ISSUES | 1 | 1 | Alpha import is forbidden |" in index_content
    assert "| Beta | 1 | Beta layering should be simplified |" in index_content
    assert "| Gamma | 1 |" in index_content


def test_standard_run_index_has_no_navigation_or_debug_sections(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc).generate(output_file=str(out))

    index_content = (out / "report.md").read_text(encoding="utf-8")
    assert "(targets/" not in index_content
    assert "## Matching Debug" not in index_content
    assert "## Raw Evidence" not in index_content
    assert "## Full Result Table" not in index_content
    assert "| Target | Path | Exit | Results | Failed |" not in index_content


def test_standard_orders_run_overview_before_target_groups(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc).generate(output_file=str(out))

    index_content = (out / "report.md").read_text(encoding="utf-8")
    at_a_glance_pos = index_content.index("## At a glance")
    issues_pos = index_content.index("## Projects with issues")
    warnings_pos = index_content.index("## Projects with warnings only")
    passed_pos = index_content.index(
        "<summary><strong>Passed projects (1)</strong></summary>"
    )
    metadata_pos = index_content.index("## Run metadata")

    assert at_a_glance_pos < issues_pos < warnings_pos < passed_pos < metadata_pos


def test_standard_triage_layout_sorts_issues_and_filters_pass_only_hotspots(tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(_triage_doc()).generate(output_file=str(out))

    index_content = (out / "report.md").read_text(encoding="utf-8")
    assert "## Common failure causes" in index_content
    alpha_row = "| Alpha | ERROR | 1 | 1 | Alpha renderer crashed |"
    beta_row = "| Beta | ISSUES | 1 | 1 | Beta import is forbidden |"
    gamma_row = "| Gamma | 1 | Gamma dependency is discouraged |"
    delta_row = "| Delta | 2 |"
    assert alpha_row in index_content
    assert beta_row in index_content
    assert gamma_row in index_content
    assert delta_row in index_content
    assert index_content.index(alpha_row) < index_content.index(beta_row)
    assert "| `arch/shared-rule` | 2 | 2 |" in index_content
    assert "| `arch/warn-rule` | 1 | 1 |" in index_content
    assert "arch/pass-only" not in index_content
    assert "- Exit policy: any_fail" in index_content


def test_standard_hides_common_failure_causes_when_no_projects_have_issues(tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(_warnings_and_passes_doc()).generate(output_file=str(out))

    index_content = (out / "report.md").read_text(encoding="utf-8")
    assert "## Projects with issues" in index_content
    assert "No projects with issues." in index_content
    assert "## Common failure causes" not in index_content
    assert "## Projects with warnings only" in index_content
    assert "<summary><strong>Passed projects (1)</strong></summary>" in index_content


def test_standard_cleans_existing_targets_directory(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc, markdown_mode="verbose").generate(
        output_file=str(out)
    )

    assert (out / "targets" / "alpha.md").is_file()

    MarkdownReportGenerator(multi_doc).generate(output_file=str(out))

    assert (out / "report.md").is_file()
    assert not (out / "targets").exists()


def test_verbose_writes_target_pages(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc, markdown_mode="verbose").generate(
        output_file=str(out)
    )

    assert (out / "targets" / "alpha.md").is_file()
    assert (out / "targets" / "beta.md").is_file()
    assert (out / "targets" / "gamma.md").is_file()


def test_verbose_target_has_rule_details_without_debug_appendices(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc, markdown_mode="verbose").generate(
        output_file=str(out)
    )

    alpha_content = (out / "targets" / "alpha.md").read_text(encoding="utf-8")
    assert "## Issue Summary by Rule" in alpha_content
    assert "## Rule Details" in alpha_content
    assert "## Matching Debug" not in alpha_content


def test_verbose_run_index_uses_triage_layout_with_linked_target_rows(
    multi_doc, tmp_path
):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc, markdown_mode="verbose").generate(
        output_file=str(out)
    )

    index_content = (out / "report.md").read_text(encoding="utf-8")
    _assert_section_order(
        index_content,
        [
            "## At a glance",
            "## Projects with issues",
            "## Common failure causes",
            "## Projects with warnings only",
            "<summary><strong>Passed projects (1)</strong></summary>",
            "## Run metadata",
        ],
    )
    assert "> **Verdict:** ISSUES" in index_content
    assert (
        "| [Alpha](targets/alpha.md) | ISSUES | 1 | 1 | "
        "Alpha import is forbidden |" in index_content
    )
    assert (
        "| [Beta](targets/beta.md) | 1 | Beta layering should be simplified |"
        in index_content
    )
    assert "| [Gamma](targets/gamma.md) | 1 |" in index_content
    assert "## Targets With Issues" not in index_content
    assert "## Warnings Only" not in index_content
    assert "## OK Targets" not in index_content
    assert "## Rule Hotspots" not in index_content


def test_debug_keeps_bundle_shape_and_appends_target_debug(multi_doc, tmp_path):
    verbose_out = tmp_path / "verbose"
    debug_out = tmp_path / "debug"

    MarkdownReportGenerator(multi_doc, markdown_mode="verbose").generate(
        output_file=str(verbose_out)
    )
    MarkdownReportGenerator(multi_doc, markdown_mode="debug").generate(
        output_file=str(debug_out)
    )

    verbose_files = {p.relative_to(verbose_out) for p in verbose_out.rglob("*.md")}
    debug_files = {p.relative_to(debug_out) for p in debug_out.rglob("*.md")}
    assert verbose_files == debug_files

    alpha_content = (debug_out / "targets" / "alpha.md").read_text(encoding="utf-8")
    assert "## Matching Debug" in alpha_content
    assert "## Raw Evidence" in alpha_content
    assert "## Full Result Table" in alpha_content

    debug_index = (debug_out / "report.md").read_text(encoding="utf-8")
    assert "## At a glance" in debug_index
    assert "## Projects with issues" in debug_index
    assert "## Matching Debug" not in debug_index
    assert "## Raw Evidence" not in debug_index
    assert "## Full Result Table" not in debug_index

    compact_passed_pos = alpha_content.index("## Compact Passed Summary")
    matching_debug_pos = alpha_content.index("## Matching Debug")
    assert compact_passed_pos < matching_debug_pos
