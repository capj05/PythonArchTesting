"""
Tests for JSON report generation and serialization.
"""

import json
from datetime import datetime
from typing import List

import pytest

from pythonarchtesting.report.api import build_report, generate_validation_report
from pythonarchtesting.report.renderers.json import render_json
from pythonarchtesting.report.ir.builder import build_report_ir
from pythonarchtesting.state import ProjectState, ValidationResult, ValidationStatus


@pytest.fixture
def single_project_state(tmp_path) -> ProjectState:
    state = ProjectState(str(tmp_path), [])
    state.initialize(str(tmp_path))
    return state


def _sample_results(project_name: str) -> List[ValidationResult]:
    return [
        ValidationResult(
            status=ValidationStatus.WARNING,
            description="Second check",
            check_type="beta",
            src_function_name="b_func",
            src_package="pkg_b",
            src_line_num=10,
            src_file="b.py",
            target_function_name="b_ref",
            target_package="ref_b",
            project_name=project_name,
            timestamp=2.0,
            details={},
        ),
        ValidationResult(
            status=ValidationStatus.OK,
            description="First check",
            check_type="alpha",
            src_function_name="a_func",
            src_package="pkg_a",
            src_line_num=5,
            src_file="a.py",
            target_function_name="a_ref",
            target_package="ref_a",
            project_name=project_name,
            timestamp=1.0,
            details={},
        ),
    ]


def test_schema_v2_root_fields(single_project_state):
    results = _sample_results("project_one")
    for result in results:
        single_project_state.add_validation_result(result)

    report = render_json(build_report_ir(single_project_state))
    data = json.loads(report)

    assert data["schema_version"] == "2"
    assert isinstance(data["framework_version"], str)
    assert data["generated_at"].endswith("Z")
    datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))

    assert "run" in data
    assert "matching" in data
    assert "summary" in data
    assert "exit_code" in data
    assert "results" in data
    by_rule = {item["rule_id"]: item for item in data["results"]}
    assert "alpha" in by_rule
    assert "beta" in by_rule
    alpha = by_rule["alpha"]
    assert alpha["project_id"]
    assert alpha["result_id"]
    assert alpha["category"]
    assert "locations" in alpha
    assert alpha["source"]["module"] == "pkg_a"
    assert alpha["source"]["qualname"] == "a_func"
    assert alpha["source"]["file"] == "a.py"
    assert alpha["source"]["line"] == 5
    assert alpha["target"]["module"] == "ref_a"
    assert alpha["target"]["qualname"] == "a_ref"


def test_schema_v2_results_sorted(single_project_state):
    results = _sample_results("project_one")
    for result in results:
        single_project_state.add_validation_result(result)

    report = generate_validation_report(single_project_state, "json")
    data = json.loads(report)

    expected = build_report(single_project_state)["results"]
    assert data["results"] == expected
