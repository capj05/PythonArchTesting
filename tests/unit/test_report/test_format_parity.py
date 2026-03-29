from __future__ import annotations

import json

from src.report.renderers.common import core_rows
from src.report.renderers.json import render_json
from src.report.renderers.markdown import render_markdown


def _sample_report() -> dict:
    return {
        "schema_version": "2",
        "framework_version": "test",
        "generated_at": "2026-02-12T00:00:00Z",
        "exit_code": 1,
        "summary": {
            "results_total": 1,
            "severity_counts": {"error": 1},
            "status_counts": {"FAILED": 1},
            "category_counts": {"arch": 1},
        },
        "matching": {"matches": []},
        "results": [
            {
                "project_id": "proj-a",
                "result_id": "abc123",
                "category": "arch",
                "rule_id": "arch/forbidden_dependency",
                "severity": "error",
                "status": "FAILED",
                "message": "Bad dep",
                "source_entity_id": "s1",
                "target_entity_id": "t1",
                "source": {
                    "module": "pkg.mod",
                    "qualname": "Cls.fn",
                    "file": "a.py",
                    "line": 7,
                },
                "target": {"module": "pkg.t", "qualname": "T.fn"},
                "evidence": [],
                "details": {},
                "fix_hints": [],
            }
        ],
    }


def test_format_parity_core_rows():
    report = _sample_report()
    expected_rows = core_rows(report["results"])

    json_output = render_json(report)
    markdown_output = render_markdown(report)

    parsed = json.loads(json_output)
    assert core_rows(parsed["results"]) == expected_rows

    for item in report["results"]:
        result_id = item["result_id"]
        rule_id = item["rule_id"]
        assert result_id in markdown_output
        assert rule_id in markdown_output
