"""Acceptance tests for single-target markdown mode rendering."""

from __future__ import annotations

from pythonarchtesting.report.ir.normalize import report_dict_to_ir
from pythonarchtesting.report.markdown_generator import MarkdownReportGenerator
from pythonarchtesting.report.renderers.markdown import render_markdown


def _ok_single_doc():
    report_dict = {
        "schema_version": "2",
        "framework_version": "test",
        "generated_at": "2026-04-12T00:00:00Z",
        "exit_code": 0,
        "run": {"target_path": "/targets/beta"},
        "summary": {
            "results_total": 1,
            "status_counts": {"OK": 1},
            "severity_counts": {"info": 1},
            "category_counts": {"arch": 1},
        },
        "matching": {"matches": []},
        "results": [
            {
                "project_id": "beta",
                "result_id": "beta-ok",
                "category": "arch",
                "rule_id": "arch/rule-ok",
                "rule_type": "arch/rule-ok",
                "severity": "info",
                "status": "OK",
                "message": "Beta rule pass",
                "source_entity_id": "s1",
                "target_entity_id": "t1",
                "source": {
                    "module": "pkg.beta",
                    "qualname": "All.good",
                    "file": "beta.py",
                    "line": 1,
                },
                "target": {
                    "module": "pkg.target",
                    "qualname": "All.good",
                    "file": "target.py",
                    "line": 1,
                },
                "evidence": [],
                "details": {},
                "fix_hints": [],
            }
        ],
    }
    return report_dict_to_ir(report_dict, kind="single")


def test_default_mode_is_standard(single_doc):
    rendered = MarkdownReportGenerator(single_doc).generate()

    assert "# Validation Report" in rendered
    assert "## Verdict" in rendered
    assert "## Short Issue Summary" in rendered


def test_explicit_standard_via_render_markdown_matches_no_mode(single_doc):
    no_mode = MarkdownReportGenerator(single_doc).generate()
    explicit_standard = render_markdown(single_doc, markdown_mode="standard")

    assert no_mode == explicit_standard


def test_standard_has_required_compact_sections(single_doc):
    rendered = MarkdownReportGenerator(single_doc).generate()

    assert "## Verdict" in rendered
    assert "## Summary" in rendered
    assert "- Total results: 3" in rendered
    assert "## Short Issue Summary" in rendered
    assert "Alpha import is forbidden" in rendered
    assert "## Warnings Only" in rendered
    assert "Alpha layer naming should be tightened" in rendered
    assert "## Rule Hotspots" in rendered


def test_standard_hides_verbose_and_debug_sections(single_doc):
    rendered = MarkdownReportGenerator(single_doc).generate()

    assert "## Issue Summary by Rule" not in rendered
    assert "## Rule Details" not in rendered
    assert "## Compact Passed Summary" not in rendered
    assert "## Matching Debug" not in rendered
    assert "## Raw Evidence" not in rendered
    assert "## Full Result Table" not in rendered
    assert "## Internal Diagnostics" not in rendered
    assert "Matching note:" not in rendered


def test_standard_ok_target_shows_ok_summary():
    rendered = MarkdownReportGenerator(_ok_single_doc()).generate()

    assert "## Short Issue Summary" in rendered
    assert "No failing rules." in rendered
    assert "## OK Summary" in rendered
    assert "- No actionable issues." in rendered
    assert "- Passed checks: 1" in rendered


def test_standard_orders_overview_before_issue_summary_and_hotspots(single_doc):
    rendered = MarkdownReportGenerator(single_doc).generate()

    verdict_pos = rendered.index("## Verdict")
    summary_pos = rendered.index("## Summary")
    short_issue_pos = rendered.index("## Short Issue Summary")
    hotspots_pos = rendered.index("## Rule Hotspots")

    assert verdict_pos < summary_pos < short_issue_pos < hotspots_pos


def test_verbose_has_issue_summary_and_rule_details(single_doc):
    rendered = MarkdownReportGenerator(single_doc, markdown_mode="verbose").generate()

    assert "## Issue Summary by Rule" in rendered
    assert "## Rule Details" in rendered
    assert "## Compact Passed Summary" in rendered
    assert "## Matching Debug" not in rendered


def test_debug_appends_debug_sections_after_verbose_content(single_doc):
    rendered = MarkdownReportGenerator(single_doc, markdown_mode="debug").generate()

    assert "## Matching Debug" in rendered
    assert "## Raw Evidence" in rendered
    assert "## Full Result Table" in rendered

    rule_details_pos = rendered.index("## Rule Details")
    matching_debug_pos = rendered.index("## Matching Debug")
    assert rule_details_pos < matching_debug_pos
