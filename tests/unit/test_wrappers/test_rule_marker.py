"""
Tests for passive rule marker behavior.
"""

import importlib
from typing import Annotated, get_args, get_origin

import pytest

from pythonarchtesting.rules.declaration.utils import RuleSeverity, get_rule_specs


def _rules_api():
    from pythonarchtesting import rules

    return rules


def test_configured_helpers_return_rule_markers() -> None:
    rules = _rules_api()
    signature_marker = rules.required_entity_signature(mode="exact")
    method_marker = rules.required_method(signature_mode="exact", declared_only=True)
    factory_marker = rules.required_factory(name_match="exact")
    import_marker = rules.forbid_imports("statistics", scope="package")
    protocol_marker = rules.implements_protocol("sample.Repository")
    enum_marker = rules.is_enum()

    for marker in (
        signature_marker,
        method_marker,
        factory_marker,
        import_marker,
        protocol_marker,
        enum_marker,
    ):
        assert marker.__class__.__name__ == "RuleMarker"
        assert get_rule_specs(marker) == []

    assert method_marker.params["declared_only"] is True
    assert factory_marker.kind == "required_factory"
    assert enum_marker.kind == "is_enum"


def test_rule_markers_are_passive_metadata_objects() -> None:
    marker = _rules_api().forbid_imports("statistics", scope="package")

    assert marker.kind == "forbid_imports"
    assert marker.params["mode"] == "reachable"
    assert marker.message is None
    assert marker.severity == RuleSeverity.ERROR
    assert not callable(marker)


def test_rule_markers_can_be_used_as_annotated_metadata() -> None:
    rules = _rules_api()
    annotation = Annotated[
        None,
        rules.required_entity_signature(mode="compatible"),
        rules.implements_protocol("sample.Repository"),
    ]

    assert get_origin(annotation) is Annotated

    metadata = get_args(annotation)[1:]
    assert len(metadata) == 2
    assert all(item.__class__.__name__ == "RuleMarker" for item in metadata)
    assert metadata[0].kind == "required_entity_signature"
    assert metadata[1].kind == "implements_protocol"


def test_rule_markers_convert_to_rule_specs() -> None:
    marker = _rules_api().required_entity_signature(mode="exact", severity="warning")
    spec = marker.to_spec(order=3)

    assert spec.kind == "required_entity_signature"
    assert spec.order == 3
    assert spec.params["mode"] == "exact"
    assert spec.params["severity"] == "warning"
    assert spec.severity == RuleSeverity.WARNING


def test_rule_spec_helpers_remain_compatibility_only_imports() -> None:
    rules = importlib.import_module("pythonarchtesting.rules")
    utils = importlib.import_module("pythonarchtesting.rules.declaration.utils")

    assert not hasattr(rules, "RuleSpec")
    assert hasattr(utils, "RuleSpec")
    assert hasattr(utils, "add_rule_spec")
    assert hasattr(utils, "get_rule_specs")


def test_forbid_imports_rejects_invalid_mode() -> None:
    with pytest.raises(
        ValueError,
        match="forbid_imports\\(\\) mode must be 'reachable' or 'direct'\\.",
    ):
        _rules_api().forbid_imports("statistics", mode="invalid")
