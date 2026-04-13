"""Acceptance tests for multi-target markdown bundle mode rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from pythonarchtesting.report.markdown_generator import MarkdownReportGenerator


# ---------------------------------------------------------------------------
# Default / standard
# ---------------------------------------------------------------------------


def test_standard_index_has_no_matching_debug(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc).generate(output_file=str(out))

    index_content = (out / "report.md").read_text(encoding="utf-8")
    assert "## Matching Debug" not in index_content


def test_standard_target_pages_have_no_matching_debug(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc).generate(output_file=str(out))

    alpha_content = (out / "targets" / "alpha.md").read_text(encoding="utf-8")
    assert "## Matching Debug" not in alpha_content


def test_standard_target_pages_exist(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc).generate(output_file=str(out))

    assert (out / "targets" / "alpha.md").is_file()
    assert (out / "targets" / "beta.md").is_file()


def test_standard_target_pages_have_no_full_results_table(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc).generate(output_file=str(out))

    alpha_content = (out / "targets" / "alpha.md").read_text(encoding="utf-8")
    assert "## Results" not in alpha_content


def test_standard_target_page_has_failed_results_list(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc).generate(output_file=str(out))

    alpha_content = (out / "targets" / "alpha.md").read_text(encoding="utf-8")
    assert "## Failed Results" in alpha_content
    assert "Alpha import is forbidden" in alpha_content


# ---------------------------------------------------------------------------
# Verbose
# ---------------------------------------------------------------------------


def test_verbose_writes_target_pages(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc, markdown_mode="verbose").generate(
        output_file=str(out)
    )

    assert (out / "targets" / "alpha.md").is_file()
    assert (out / "targets" / "beta.md").is_file()


def test_verbose_target_has_rule_details(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc, markdown_mode="verbose").generate(
        output_file=str(out)
    )

    alpha_content = (out / "targets" / "alpha.md").read_text(encoding="utf-8")
    assert "## Rule Details" in alpha_content


def test_verbose_target_has_no_matching_debug(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc, markdown_mode="verbose").generate(
        output_file=str(out)
    )

    alpha_content = (out / "targets" / "alpha.md").read_text(encoding="utf-8")
    assert "## Matching Debug" not in alpha_content


# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------


def test_debug_target_has_matching_debug(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    MarkdownReportGenerator(multi_doc, markdown_mode="debug").generate(
        output_file=str(out)
    )

    alpha_content = (out / "targets" / "alpha.md").read_text(encoding="utf-8")
    assert "## Matching Debug" in alpha_content


def test_debug_bundle_shape_same_as_verbose(multi_doc, tmp_path):
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


# ---------------------------------------------------------------------------
# Parity (step 12)
# ---------------------------------------------------------------------------


def test_verbose_single_and_multi_both_have_rule_details(single_doc, multi_doc, tmp_path):
    single_rendered = MarkdownReportGenerator(
        single_doc, markdown_mode="verbose"
    ).generate()

    multi_out = tmp_path / "multi"
    MarkdownReportGenerator(multi_doc, markdown_mode="verbose").generate(
        output_file=str(multi_out)
    )
    alpha_content = (multi_out / "targets" / "alpha.md").read_text(encoding="utf-8")

    assert "## Rule Details" in single_rendered
    assert "## Rule Details" in alpha_content
