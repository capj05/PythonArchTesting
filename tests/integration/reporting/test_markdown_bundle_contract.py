"""Acceptance tests for markdown bundle path stability and doc consistency."""

from __future__ import annotations

from pathlib import Path

from pythonarchtesting.report.markdown_generator import MarkdownReportGenerator
from pythonarchtesting.report.paths import markdown_bundle_index, markdown_target_page


# ---------------------------------------------------------------------------
# Bundle stability (step 11)
# ---------------------------------------------------------------------------


def test_bundle_index_path():
    root = Path("bundle-root")
    assert markdown_bundle_index(root) == root / "report.md"


def test_bundle_target_page_path():
    root = Path("bundle-root")
    assert markdown_target_page(root, "x") == root / "targets" / "x.md"


def test_mode_does_not_change_bundle_root_filename_verbose(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    index_path = MarkdownReportGenerator(multi_doc, markdown_mode="verbose").generate(
        output_file=str(out)
    )
    assert Path(index_path).name == "report.md"


def test_mode_does_not_change_bundle_root_filename_debug(multi_doc, tmp_path):
    out = tmp_path / "bundle"
    index_path = MarkdownReportGenerator(multi_doc, markdown_mode="debug").generate(
        output_file=str(out)
    )
    assert Path(index_path).name == "report.md"


def test_single_target_is_not_a_bundle(single_doc):
    result = MarkdownReportGenerator(single_doc).generate()
    assert isinstance(result, str)
    assert result.startswith("# Validation Report")


# ---------------------------------------------------------------------------
# Doc consistency (step 14)
# ---------------------------------------------------------------------------


def test_defaults_conf_has_markdown_mode():
    import importlib.resources

    conf_text = (
        importlib.resources.files("pythonarchtesting")
        .joinpath("defaults.conf")
        .read_text(encoding="utf-8")
    )
    assert "markdown_mode" in conf_text


def test_reporting_doc_mentions_three_modes():
    doc_path = Path(__file__).parents[3] / "docs" / "reporting.md"
    doc_text = doc_path.read_text(encoding="utf-8")
    assert "standard" in doc_text
    assert "verbose" in doc_text
    assert "debug" in doc_text


def test_reporting_doc_mentions_markdown_mode_flag():
    doc_path = Path(__file__).parents[3] / "docs" / "reporting.md"
    doc_text = doc_path.read_text(encoding="utf-8")
    assert "--markdown-mode" in doc_text
