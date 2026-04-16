"""Acceptance tests for multi-target markdown bundle mode rendering."""

from __future__ import annotations

from pathlib import Path

from pythonarchtesting.report.markdown_generator import MarkdownReportGenerator


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
    assert "## Verdict" in index_content
    assert "## Summary" in index_content
    assert "## Targets With Issues" in index_content
    assert "## Warnings Only" in index_content
    assert "## OK Targets" in index_content
    assert "## Rule Hotspots" in index_content
    assert "- alpha: status `ISSUES`; exit 1; issues 1; warnings 0" in index_content
    assert "- beta: status `WARNINGS ONLY`; exit 0; issues 0; warnings 1" in index_content
    assert "- gamma: status `OK`; exit 0; issues 0; warnings 0" in index_content


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
    verdict_pos = index_content.index("## Verdict")
    summary_pos = index_content.index("## Summary")
    issues_pos = index_content.index("## Targets With Issues")
    hotspots_pos = index_content.index("## Rule Hotspots")

    assert verdict_pos < summary_pos < issues_pos < hotspots_pos


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

    rule_details_pos = alpha_content.index("## Rule Details")
    matching_debug_pos = alpha_content.index("## Matching Debug")
    assert rule_details_pos < matching_debug_pos
