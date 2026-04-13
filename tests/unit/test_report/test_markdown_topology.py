from __future__ import annotations

from pathlib import Path

import pytest

from pythonarchtesting.report.ir.normalize import report_dict_to_ir
from pythonarchtesting.report.markdown_generator import MarkdownReportGenerator
from pythonarchtesting.report.paths import markdown_bundle_index, markdown_target_page


def _single_report() -> dict:
    return {
        "schema_version": "2",
        "framework_version": "test",
        "generated_at": "2026-04-12T00:00:00Z",
        "exit_code": 1,
        "run": {"target_path": "/targets/alpha"},
        "summary": {
            "results_total": 1,
            "status_counts": {"FAILED": 1},
            "severity_counts": {"error": 1},
            "category_counts": {"arch": 1},
        },
        "matching": {"matches": []},
        "results": [
            {
                "project_id": "alpha",
                "result_id": "alpha-fail",
                "category": "arch",
                "rule_id": "arch/rule-a",
                "severity": "error",
                "status": "FAILED",
                "message": "Alpha failed",
                "source_entity_id": "s1",
                "target_entity_id": "t1",
                "source": {
                    "module": "pkg.alpha",
                    "qualname": "Service.run",
                    "file": "alpha.py",
                    "line": 10,
                },
                "target": {
                    "module": "pkg.target",
                    "qualname": "Service.run",
                    "file": "target.py",
                    "line": 11,
                },
                "evidence": [],
                "details": {},
                "fix_hints": [],
            }
        ],
    }


def _multi_report() -> dict:
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
                "results_total": 1,
                "status_counts": {"FAILED": 1},
                "severity_counts": {"error": 1},
                "category_counts": {"arch": 1},
            },
        },
        "targets": [
            {
                "target_id": "alpha",
                "display_name": "Alpha",
                "target_path": "/targets/alpha",
                "exit_code": 1,
                "summary": {
                    "results_total": 1,
                    "status_counts": {"FAILED": 1},
                    "severity_counts": {"error": 1},
                    "category_counts": {"arch": 1},
                },
                "matching": {"matches": []},
                "results": [
                    {
                        "project_id": "alpha",
                        "result_id": "alpha-fail",
                        "category": "arch",
                        "rule_id": "arch/rule-a",
                        "severity": "error",
                        "status": "FAILED",
                        "message": "Alpha failed",
                        "source_entity_id": "s1",
                        "target_entity_id": "t1",
                        "source": {
                            "module": "pkg.alpha",
                            "qualname": "Service.run",
                            "file": "alpha.py",
                            "line": 10,
                        },
                        "target": {
                            "module": "pkg.target",
                            "qualname": "Service.run",
                            "file": "target.py",
                            "line": 11,
                        },
                        "evidence": [],
                        "details": {},
                        "fix_hints": [],
                    }
                ],
            },
            {
                "target_id": "beta",
                "display_name": "Beta",
                "target_path": "/targets/beta",
                "exit_code": 0,
                "summary": {
                    "results_total": 0,
                    "status_counts": {},
                    "severity_counts": {},
                    "category_counts": {},
                },
                "matching": {"matches": []},
                "results": [],
            },
        ],
    }


def test_single_target_markdown_generation_returns_inline_document() -> None:
    document = report_dict_to_ir(_single_report(), kind="single")

    rendered = MarkdownReportGenerator(document).generate()

    assert rendered.startswith("# Validation Report")
    assert "Alpha failed" in rendered


def test_multi_target_markdown_generation_requires_output_directory() -> None:
    document = report_dict_to_ir(_multi_report(), kind="multi")

    with pytest.raises(
        ValueError,
        match="Multi-target markdown reporting requires an output directory path.",
    ):
        MarkdownReportGenerator(document).generate()


def test_multi_target_markdown_generation_writes_bundle_layout(tmp_path: Path) -> None:
    document = report_dict_to_ir(_multi_report(), kind="multi")
    output_root = tmp_path / "markdown_bundle"

    index_path = MarkdownReportGenerator(document).generate(output_file=str(output_root))

    assert index_path == str(output_root / "report.md")
    assert (output_root / "report.md").is_file()
    assert (output_root / "targets" / "alpha.md").is_file()
    assert (output_root / "targets" / "beta.md").is_file()


def test_markdown_bundle_paths_remain_stable() -> None:
    root = Path("bundle-root")

    assert markdown_bundle_index(root) == root / "report.md"
    assert markdown_target_page(root, "alpha") == root / "targets" / "alpha.md"
