"""Acceptance tests for single-target markdown mode rendering.

Standard mode: MarkdownReportGenerator(doc).generate() — no markdown_mode arg.
Verbose/Debug: MarkdownReportGenerator(doc, markdown_mode=...).generate().
"""

from __future__ import annotations

import pytest

from pythonarchtesting.report.markdown_generator import MarkdownReportGenerator
from pythonarchtesting.report.renderers.markdown import render_markdown


# ---------------------------------------------------------------------------
# Default mode (step 8)
# ---------------------------------------------------------------------------


def test_default_mode_is_standard(single_doc):
    rendered = MarkdownReportGenerator(single_doc).generate()

    assert "# Validation Report" in rendered
    assert "## Matching Debug" not in rendered


def test_explicit_standard_via_render_markdown_matches_no_mode(single_doc):
    no_mode = MarkdownReportGenerator(single_doc).generate()
    explicit_standard = render_markdown(single_doc, markdown_mode="standard")

    assert no_mode == explicit_standard


# ---------------------------------------------------------------------------
# Section presence/absence (step 9)
# ---------------------------------------------------------------------------


def test_standard_has_no_matching_debug(single_doc):
    rendered = MarkdownReportGenerator(single_doc).generate()

    assert "## Matching Debug" not in rendered


def test_standard_has_no_rule_detail_blocks(single_doc):
    rendered = MarkdownReportGenerator(single_doc).generate()

    assert "## Rule Details" not in rendered


def test_standard_has_no_full_results_table(single_doc):
    rendered = MarkdownReportGenerator(single_doc).generate()

    assert "## Results" not in rendered


def test_standard_has_failed_results_list(single_doc):
    rendered = MarkdownReportGenerator(single_doc).generate()

    assert "## Failed Results" in rendered
    assert "Alpha import is forbidden" in rendered


def test_standard_omits_failed_results_section_when_no_failures(multi_doc):
    from pythonarchtesting.report.ir.normalize import report_dict_to_ir

    # Build a single doc with no failures
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
                "rule_id": "arch/rule-b",
                "severity": "info",
                "status": "OK",
                "message": "Beta rule pass",
                "source_entity_id": "s1",
                "target_entity_id": "t1",
                "source": {"module": "pkg.beta", "qualname": "All.good", "file": "beta.py", "line": 1},
                "target": {"module": "pkg.target", "qualname": "All.good", "file": "target.py", "line": 1},
                "evidence": [],
                "details": {},
                "fix_hints": [],
            }
        ],
    }
    doc = report_dict_to_ir(report_dict, kind="single")
    rendered = MarkdownReportGenerator(doc).generate()

    assert "## Failed Results" not in rendered


def test_verbose_has_issue_summary_by_rule(single_doc):
    rendered = MarkdownReportGenerator(single_doc, markdown_mode="verbose").generate()

    assert "## Issue Summary by Rule" in rendered


def test_verbose_has_rule_details(single_doc):
    rendered = MarkdownReportGenerator(single_doc, markdown_mode="verbose").generate()

    assert "## Rule Details" in rendered


def test_verbose_has_no_matching_debug(single_doc):
    rendered = MarkdownReportGenerator(single_doc, markdown_mode="verbose").generate()

    assert "## Matching Debug" not in rendered


def test_debug_has_matching_debug(single_doc):
    rendered = MarkdownReportGenerator(single_doc, markdown_mode="debug").generate()

    assert "## Matching Debug" in rendered


def test_debug_has_all_verbose_sections(single_doc):
    rendered = MarkdownReportGenerator(single_doc, markdown_mode="debug").generate()

    assert "## Issue Summary by Rule" in rendered
    assert "## Rule Details" in rendered


# ---------------------------------------------------------------------------
# Reading order (step 10)
# ---------------------------------------------------------------------------


def test_standard_exit_code_before_failed_results(single_doc):
    rendered = MarkdownReportGenerator(single_doc).generate()

    exit_code_pos = rendered.index("**Exit Code:**")
    failed_results_pos = rendered.index("## Failed Results")
    assert exit_code_pos < failed_results_pos


def test_verbose_exit_code_before_rule_details(single_doc):
    rendered = MarkdownReportGenerator(single_doc, markdown_mode="verbose").generate()

    exit_code_pos = rendered.index("**Exit Code:**")
    rule_details_pos = rendered.index("## Rule Details")
    assert exit_code_pos < rule_details_pos


def test_debug_verbose_sections_before_matching_debug(single_doc):
    rendered = MarkdownReportGenerator(single_doc, markdown_mode="debug").generate()

    rule_details_pos = rendered.index("## Rule Details")
    matching_debug_pos = rendered.index("## Matching Debug")
    assert rule_details_pos < matching_debug_pos


# ---------------------------------------------------------------------------
# Regression (step 13)
# ---------------------------------------------------------------------------


def test_regression_no_matching_debug_in_standard(single_doc):
    rendered = MarkdownReportGenerator(single_doc).generate()

    assert "Matching Debug" not in rendered


def test_regression_no_full_results_table_in_standard(single_doc):
    rendered = MarkdownReportGenerator(single_doc).generate()

    assert "## Results" not in rendered
