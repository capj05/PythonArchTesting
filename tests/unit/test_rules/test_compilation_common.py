from __future__ import annotations

from tests.unit.test_rules.protocol_rule_test_helpers import extract_entity

from pythonarchtesting.rules.compilation.common import (
    build_invalid_param_sentinel_rule,
    with_rule_id_suffix,
)


_SOURCE = """
class TestContract:
    pass
"""


def _entity():
    return extract_entity(_SOURCE, role="source", kind="class", name="TestContract")


def test_build_invalid_param_sentinel_rule_sets_decorator_name_and_rule_id() -> None:
    sentinel = build_invalid_param_sentinel_rule(
        _entity(),
        decorator_name="require_method_set",
        rule_id_prefix="API005/require_method_set/invalid_declaration",
        param="name_match",
        value="alias",
        valid=["any", "names", "regex"],
        reason="name_match must be one of: any, regex, names",
    )

    assert sentinel.rule_type == "compiler_invalid_param"
    assert sentinel.name == "require_method_set"
    assert (
        sentinel.rule_id
        == "API005/require_method_set/invalid_declaration/name_match"
    )
    assert sentinel.params["decorator"] == "require_method_set"
    assert sentinel.params["param"] == "name_match"
    assert sentinel.params["value"] == "alias"
    assert sentinel.params["valid"] == ["any", "names", "regex"]
    assert sentinel.params["compiler_reason"] == (
        "name_match must be one of: any, regex, names"
    )
    assert sentinel.params["fail_on_unmatched"] is True
    assert sentinel.severity == "error"
    assert sentinel.enabled is True


def test_build_invalid_param_sentinel_rule_appends_suffix() -> None:
    sentinel = build_invalid_param_sentinel_rule(
        _entity(),
        decorator_name="require_method_set",
        rule_id_prefix="API005/require_method_set/invalid_declaration",
        param="min_count",
        value=-1,
        valid=None,
        reason="min_count must be an integer >= 0",
        rule_id_suffix="/d2",
    )

    assert (
        sentinel.rule_id
        == "API005/require_method_set/invalid_declaration/min_count/d2"
    )
    assert sentinel.params["valid"] == []


def test_build_invalid_param_sentinel_rule_fix_hint_uses_valid_list() -> None:
    sentinel = build_invalid_param_sentinel_rule(
        _entity(),
        decorator_name="required_factory",
        rule_id_prefix="API004/required_factory/invalid_param",
        param="detection_mode",
        value="bogus",
        valid=["extended", "strict"],
        reason="detection_mode must be one of: extended, strict",
    )

    assert sentinel.fix_hints == ("Use one of: extended, strict",)


def test_build_invalid_param_sentinel_rule_fix_hint_falls_back_to_reason() -> None:
    sentinel = build_invalid_param_sentinel_rule(
        _entity(),
        decorator_name="require_method_set",
        rule_id_prefix="API005/require_method_set/invalid_declaration",
        param="pattern",
        value=None,
        valid=None,
        reason="pattern must be a non-empty string",
    )

    assert sentinel.fix_hints == ("pattern must be a non-empty string",)


def test_build_invalid_param_sentinel_rule_fix_hint_default_when_no_context() -> None:
    sentinel = build_invalid_param_sentinel_rule(
        _entity(),
        decorator_name="require_method_set",
        rule_id_prefix="API005/require_method_set/invalid_declaration",
        param="custom",
    )

    assert sentinel.fix_hints == ("Provide a valid value for the parameter.",)
    assert sentinel.params["compiler_reason"] is None


def test_with_rule_id_suffix_returns_unchanged_when_empty() -> None:
    assert with_rule_id_suffix("API005/foo") == "API005/foo"
    assert with_rule_id_suffix("API005/foo", "") == "API005/foo"


def test_with_rule_id_suffix_appends_suffix() -> None:
    assert with_rule_id_suffix("API005/foo", "/d3") == "API005/foo/d3"
