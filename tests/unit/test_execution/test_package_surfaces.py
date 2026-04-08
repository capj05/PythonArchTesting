from __future__ import annotations

import importlib


def test_core_package_no_longer_exports_legacy_context_symbols() -> None:
    core = importlib.import_module("pythonarchtesting.core")

    for removed in (
        "RunContext",
        "TargetResult",
        "PerTargetCaches",
        "ReportBuffer",
        "DefaultReportBuffer",
        "create_run_context",
    ):
        assert not hasattr(core, removed)

    assert core.__all__ == []


def test_execution_package_no_longer_exports_generic_evaluator_helpers() -> None:
    execution = importlib.import_module("pythonarchtesting.execution")

    for removed in (
        "EvaluationContext",
        "RuleEvaluator",
        "RuleResult",
        "evaluate_all",
        "TypeCheckEvaluator",
    ):
        assert not hasattr(execution, removed)

    assert execution.__all__ == []


def test_execution_evaluators_package_remains_the_active_surface() -> None:
    evaluators = importlib.import_module("pythonarchtesting.execution.evaluators")

    assert hasattr(evaluators, "get_rule_evaluator")
    assert hasattr(evaluators, "register_rule_evaluator")
    assert hasattr(evaluators, "ApiSignatureEvaluator")
