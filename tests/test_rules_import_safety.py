from __future__ import annotations

import importlib
import subprocess
import sys


def test_rules_import_stays_lightweight() -> None:
    code = """
import json
import sys

before = set(sys.modules)
import pythonarchtesting.rules
after = set(sys.modules)

forbidden = {
    "pythonarchtesting.execution",
    "pythonarchtesting.report",
    "pythonarchtesting.runtime",
    "sqlalchemy",
}
loaded = sorted(name for name in (after - before) if name in forbidden)
print(json.dumps({"loaded": loaded}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '{"loaded": []}'


def test_rules_public_surface_is_core_only() -> None:
    rules = importlib.import_module("pythonarchtesting.rules")

    expected = {
        "required_entity_signature",
        "required_method",
        "forbid_imports",
        "implements_protocol",
        "flow",
        "enforce_flow",
    }
    assert set(rules.__all__) == expected

    for removed in (
        "list_comprehension",
        "detect_singleton",
        "forbid_dependencies",
        "forbid_calls",
        "dynamic_imports_observed",
        "no_god_class",
        "Rule",
        "RuleResult",
        "EvalContext",
        "Evidence",
        "ArchRule",
        "RuleSelector",
        "Severity",
        "Scope",
        "EvidenceType",
        "EvidenceSource",
        "RuleStatus",
        "RuleEvaluator",
        "RuleSpec",
        "RuleSeverity",
        "get_rule_specs",
        "add_rule_spec",
    ):
        assert not hasattr(rules, removed)
