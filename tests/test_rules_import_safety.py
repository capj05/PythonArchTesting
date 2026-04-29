from __future__ import annotations

import importlib

from tests.utils.subprocess_imports import run_python_json


def test_rules_import_stays_lightweight() -> None:
    payload = run_python_json("""
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
""")
    assert payload == {"loaded": []}


def test_rules_public_surface_is_core_only() -> None:
    rules = importlib.import_module("pythonarchtesting.rules")

    expected = {
        "required_entity_signature",
        "required_method",
        "require_method_set",
        "require_member_set",
        "required_factory",
        "required_constructor",
        "required_attribute",
        "does_not_have",
        "forbid_imports",
        "implements_protocol",
        "subclass_of",
        "exact_type",
        "not_subclass_of",
        "inherits_directly_from",
        "is_enum",
        "is_abstract_class",
        "is_abstract_method",
        "is_concrete_class",
        "is_final_class",
        "is_final_method",
        "is_non_final_class",
        "is_non_abstract_method",
        "is_non_final_method",
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
