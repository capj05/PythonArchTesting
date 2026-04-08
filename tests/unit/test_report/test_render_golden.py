import json
from pathlib import Path

import pytest

from pythonarchtesting.report.ir.normalize import report_dict_to_ir
from pythonarchtesting.state import ProjectState
from pythonarchtesting.exceptions import ReportGenerationError
from pythonarchtesting.report.api import generate_validation_report
from pythonarchtesting.report.dispatcher import create_reporter
from pythonarchtesting.report.renderers.markdown import render_markdown


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
                "check_type": "arch/forbidden_dependency",
                "severity": "error",
                "status": "FAILED",
                "message": "Bad <dep> | use safe",
                "source_entity_id": "s1",
                "target_entity_id": "t1",
                "match_status": "matched",
                "confidence": 0.5,
                "source": {
                    "module": "pkg.mod",
                    "qualname": "Cls.fn",
                    "file": "a.py",
                    "line": 7,
                },
                "target": {
                    "module": "pkg.t",
                    "qualname": "T.fn",
                    "file": "b.py",
                    "line": 8,
                },
                "evidence": [
                    {
                        "type": "ast_import_graph",
                        "location": {"file": "a.py", "line": 7},
                        "payload": {"module": "x|y"},
                    }
                ],
                "details": {},
                "fix_hints": ["Remove dep"],
            }
        ],
    }


def _empty_state(tmp_path: Path) -> ProjectState:
    state = ProjectState(str(tmp_path), [])
    state.initialize(str(tmp_path))
    return state


def _golden(name: str) -> str:
    path = Path("tests/fixtures/reports") / name
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()


def _normalize(value: str) -> str:
    return value.replace("\r\n", "\n").strip()


def test_markdown_report_golden():
    rendered = render_markdown(report_dict_to_ir(_sample_report(), kind="single"))
    assert _normalize(rendered) == _golden("single_markdown.golden")


def test_dispatcher_non_db_sinks_do_not_require_sqlalchemy():
    report = _sample_report()
    for sink in ("json", "markdown"):
        reporter = create_reporter(sink, report)
        rendered = reporter.generate()
        assert isinstance(rendered, str)
    json_output = create_reporter("json", report).generate()
    parsed = json.loads(json_output)
    assert parsed["schema_version"] == "2"


def test_create_reporter_rejects_removed_html_sink():
    with pytest.raises(ValueError, match="Unsupported sink 'html'"):
        create_reporter("html", _sample_report())


def test_generate_validation_report_rejects_removed_html_format(tmp_path):
    with pytest.raises(
        ReportGenerationError,
        match="Unsupported output format 'html'. Available formats: json, markdown",
    ):
        generate_validation_report(_empty_state(tmp_path), "html")
