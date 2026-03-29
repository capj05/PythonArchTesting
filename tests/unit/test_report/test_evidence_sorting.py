from src.report.api import build_report
from src.state import ProjectState, ValidationResult, ValidationStatus


def test_evidence_sorting_none_last():
    state = ProjectState("/test", [])
    result = ValidationResult(
        status=ValidationStatus.OK,
        description="evidence sort",
        check_type="test",
        src_function_name="demo",
        details={
            "evidence": [
                {
                    "type": "runtime_calls",
                    "payload": {"filepath": None, "lineno": None, "callee": "b"},
                    "source": "runtime",
                },
                {
                    "type": "runtime_calls",
                    "payload": {"filepath": "a.py", "lineno": 1, "callee": "a"},
                    "source": "runtime",
                },
            ]
        },
    )

    state.add_validation_result(result)
    report = build_report(state)
    evidence = report["results"][0]["evidence"]
    assert evidence[0]["location"]["file"] == "a.py"
