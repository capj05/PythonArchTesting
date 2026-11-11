"""Characterisation tests of every problem ``compile_does_not_have`` reports.

The compiler checks a ``does_not_have`` declaration parameter by parameter
and drops it at the first problem: it returns a ``compiler_invalid_param``
sentinel rule plus one piece of compiler evidence. These tests pin the whole
output of each such path (the sentinel's rule ID and parameters in their
order, the evidence type, payload, location and ID) and the order of the
checks, so that a refactoring of the compiler cannot change what a dropped
declaration reports.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any, NamedTuple
from unittest.mock import Mock

import pytest

from pythonarchtesting.core.evidence import evidence_id
from pythonarchtesting.entities import DeclarationEntry, Entity
from pythonarchtesting.rules.compilation.decorators.member_absence import (
    compile_does_not_have,
)
from tests.unit.test_rules.protocol_rule_test_helpers import extract_entities

_SOURCE = """
class User:
    def dump(self) -> None:
        pass

def build() -> None:
    pass
"""
_SENTINEL_PREFIX = "NEG001/does_not_have/invalid_declaration"
_MEMBER_EVIDENCE = "compiler_invalid_member_absence_declaration"
_TARGET_EVIDENCE = "compiler_invalid_target"
_SUFFIX = "#3"


def _regex_error(pattern: str) -> str:
    """The message ``re`` gives for ``pattern``, which differs by Python."""
    try:
        re.compile(pattern)
    except re.error as exc:
        return str(exc)
    raise AssertionError(f"{pattern!r} is a valid regex")


_UNBALANCED_ERROR = _regex_error("(")
_TRAILING_ESCAPE_ERROR = _regex_error("a\\")


def _entities() -> dict[str, Entity]:
    """A class, its method, a module function and a method without a class.

    The method without a class cannot come out of extraction, so it is the
    extracted method with its qualname cut down to the bare name.
    """
    by_kind = {
        entity.kind: entity for entity in extract_entities(_SOURCE, role="source")
    }
    method = by_kind["method"]
    return {
        "class": by_kind["class"],
        "method": method,
        "function": by_kind["function"],
        "orphan_method": dataclasses.replace(method, qualname="dump"),
    }


class Case(NamedTuple):
    """One declaration and everything the compiler reports when it drops it."""

    entity: str
    params: dict[str, Any]
    issue: str
    payload_extra: dict[str, Any]
    param: str
    value: Any
    valid: list[Any] | None
    reason: str
    surface: str = "body"
    evidence_type: str = _MEMBER_EVIDENCE


_MEMBER_KINDS = ["any", "attribute", "method", "property"]
_STORAGES = ["any", "class", "instance"]
_NAME_MATCHES = ["alias", "exact", "regex"]
_SIGNATURE_MODES = ["any", "compatible", "exact"]
_SEVERITIES = ["error", "warning", "info"]

ISSUE_CASES: dict[str, Case] = {
    "compiler_invalid_surface": Case(
        "class",
        {"name": "x"},
        "compiler_invalid_surface",
        {"expected_surface": "body", "found_surface": "signature"},
        "declaration_surface",
        "signature",
        ["body"],
        "does_not_have must be declared on a class or method body",
        surface="signature",
    ),
    "compiler_invalid_target": Case(
        "function",
        {"name": "x"},
        "compiler_invalid_target",
        {"expected_kind": "class_or_method", "found_kind": "function"},
        "target_kind",
        "function",
        ["class", "method"],
        "does_not_have must target a class or method",
        evidence_type=_TARGET_EVIDENCE,
    ),
    "invalid_name/not_a_string": Case(
        "class",
        {"name": 3},
        "invalid_name",
        {"name": 3},
        "name",
        3,
        None,
        "name must be a non-empty string",
    ),
    "invalid_name/blank": Case(
        "class",
        {"name": "  "},
        "invalid_name",
        {"name": "  "},
        "name",
        "  ",
        None,
        "name must be a non-empty string",
    ),
    "invalid_member_kind": Case(
        "class",
        {"name": "x", "member_kind": "Field"},
        "invalid_member_kind",
        {"member_kind": "field"},
        "member_kind",
        "field",
        _MEMBER_KINDS,
        "member_kind must be one of: any, method, attribute, property",
    ),
    "invalid_storage": Case(
        "class",
        {"name": "x", "storage": "Slot"},
        "invalid_storage",
        {"storage": "slot"},
        "storage",
        "slot",
        _STORAGES,
        "storage must be one of: any, instance, class",
    ),
    "invalid_storage_for_member_kind/method": Case(
        "class",
        {"name": "x", "member_kind": "METHOD", "storage": "instance"},
        "invalid_storage_for_member_kind",
        {"member_kind": "method", "storage": "instance"},
        "storage",
        "instance",
        ["any"],
        "storage must be 'any' when member_kind is 'method'",
    ),
    "invalid_storage_for_member_kind/property": Case(
        "class",
        {"name": "x", "member_kind": "property", "storage": "class"},
        "invalid_storage_for_member_kind",
        {"member_kind": "property", "storage": "class"},
        "storage",
        "class",
        ["any"],
        "storage must be 'any' when member_kind is 'property'",
    ),
    "invalid_name_match": Case(
        "class",
        {"name": "x", "name_match": "Glob"},
        "invalid_name_match",
        {"name_match": "glob"},
        "name_match",
        "glob",
        _NAME_MATCHES,
        "name_match must be one of: exact, alias, regex",
    ),
    "invalid_aliases/not_a_list": Case(
        "class",
        {"name": "x", "aliases": "a"},
        "invalid_aliases",
        {"aliases": "a"},
        "aliases",
        "a",
        None,
        "aliases must be a list of non-empty strings",
    ),
    # The payload is canonicalised, which sorts lists; the sentinel keeps
    # the aliases as declared.
    "invalid_aliases/blank_alias": Case(
        "class",
        {"name": "x", "aliases": ["b", " "]},
        "invalid_aliases",
        {"aliases": [" ", "b"]},
        "aliases",
        ["b", " "],
        None,
        "aliases must be a list of non-empty strings",
    ),
    "invalid_pattern/not_a_string": Case(
        "class",
        {"name": "x", "pattern": 5},
        "invalid_pattern",
        {"pattern": 5},
        "pattern",
        5,
        None,
        "pattern must be a string",
    ),
    # The sentinel gets the stripped aliases, the payload none at all.
    "aliases_not_allowed_for_exact_name_match": Case(
        "class",
        {"name": "x", "aliases": [" b ", "a"]},
        "aliases_not_allowed_for_exact_name_match",
        {},
        "aliases",
        ["b", "a"],
        None,
        "aliases are not allowed when name_match='exact'",
    ),
    # The sentinel gets the pattern as declared, not stripped.
    "pattern_not_allowed_for_exact_name_match": Case(
        "class",
        {"name": "x", "pattern": " p "},
        "pattern_not_allowed_for_exact_name_match",
        {},
        "pattern",
        " p ",
        None,
        "pattern is not allowed when name_match='exact'",
    ),
    "missing_aliases/absent": Case(
        "class",
        {"name_match": "alias"},
        "missing_aliases",
        {},
        "aliases",
        None,
        None,
        "aliases are required when name_match='alias'",
    ),
    "missing_aliases/empty": Case(
        "class",
        {"name_match": "Alias", "aliases": []},
        "missing_aliases",
        {},
        "aliases",
        [],
        None,
        "aliases are required when name_match='alias'",
    ),
    "pattern_not_allowed_for_alias_name_match": Case(
        "class",
        {"name_match": "alias", "aliases": ["a"], "pattern": "p"},
        "pattern_not_allowed_for_alias_name_match",
        {},
        "pattern",
        "p",
        None,
        "pattern is not allowed when name_match='alias'",
    ),
    "aliases_not_allowed_for_regex_name_match": Case(
        "class",
        {"name_match": "regex", "aliases": [" a "], "pattern": "p"},
        "aliases_not_allowed_for_regex_name_match",
        {},
        "aliases",
        ["a"],
        None,
        "aliases are not allowed when name_match='regex'",
    ),
    "missing_pattern/absent": Case(
        "class",
        {"name_match": "regex"},
        "missing_pattern",
        {},
        "pattern",
        None,
        None,
        "pattern is required when name_match='regex'",
    ),
    "missing_pattern/blank": Case(
        "class",
        {"name_match": "regex", "pattern": "  "},
        "missing_pattern",
        {},
        "pattern",
        "  ",
        None,
        "pattern is required when name_match='regex'",
    ),
    "invalid_pattern/not_a_regex": Case(
        "class",
        {"name_match": "regex", "pattern": "("},
        "invalid_pattern",
        {"pattern": "(", "error": _UNBALANCED_ERROR},
        "pattern",
        "(",
        None,
        f"pattern is not a valid regex: {_UNBALANCED_ERROR}",
    ),
    # The rule keeps the stripped pattern, so the stripped one is compiled:
    # "a\\ " is a valid regex, but "a\\" left after stripping is not. Before
    # the fix the declared pattern was compiled and the rule only failed with
    # an evaluation ERROR. The sentinel and payload still report the pattern
    # as declared.
    "invalid_pattern/invalid_once_stripped": Case(
        "class",
        {"name_match": "regex", "pattern": "a\\ "},
        "invalid_pattern",
        {"pattern": "a\\ ", "error": _TRAILING_ESCAPE_ERROR},
        "pattern",
        "a\\ ",
        None,
        f"pattern is not a valid regex: {_TRAILING_ESCAPE_ERROR}",
    ),
    "invalid_signature_mode": Case(
        "class",
        {"name": "x", "signature_mode": "Loose"},
        "invalid_signature_mode",
        {"signature_mode": "loose"},
        "signature_mode",
        "loose",
        _SIGNATURE_MODES,
        "signature_mode must be one of: any, compatible, exact",
    ),
    "invalid_signature_mode_for_member_kind": Case(
        "class",
        {"name": "x", "member_kind": "attribute", "signature_mode": "exact"},
        "invalid_signature_mode_for_member_kind",
        {"signature_mode": "exact", "member_kind": "attribute"},
        "signature_mode",
        "exact",
        ["any"],
        "signature_mode must be 'any' when member_kind is 'attribute'",
    ),
    # Only a bool switches an option: "no" is no False and 1 no True.
    "invalid_include_descriptors": Case(
        "class",
        {"name": "x", "include_descriptors": "no"},
        "invalid_include_descriptors",
        {"include_descriptors": "no"},
        "include_descriptors",
        "no",
        [True, False],
        "include_descriptors must be True or False",
    ),
    "invalid_include_dynamic_attributes": Case(
        "class",
        {"name": "x", "member_kind": "method", "include_dynamic_attributes": 1},
        "invalid_include_dynamic_attributes",
        {"include_dynamic_attributes": 1},
        "include_dynamic_attributes",
        1,
        [True, False],
        "include_dynamic_attributes must be True or False",
    ),
    "include_descriptors_not_supported_for_method_kind": Case(
        "class",
        {"name": "x", "member_kind": "method", "include_descriptors": True},
        "include_descriptors_not_supported_for_method_kind",
        {"member_kind": "method"},
        "include_descriptors",
        True,
        [False],
        "include_descriptors is not supported when member_kind='method'",
    ),
    "include_dynamic_attributes_not_supported_for_method_kind": Case(
        "class",
        {"name": "x", "member_kind": "method", "include_dynamic_attributes": True},
        "include_dynamic_attributes_not_supported_for_method_kind",
        {"member_kind": "method"},
        "include_dynamic_attributes",
        True,
        [False],
        "include_dynamic_attributes is not supported when member_kind='method'",
    ),
    "invalid_member_kind_for_method_body": Case(
        "method",
        {"member_kind": "attribute"},
        "invalid_member_kind_for_method_body",
        {"member_kind": "attribute"},
        "member_kind",
        "attribute",
        ["method", "any"],
        "member_kind must be 'method' or 'any' when declared on a method body",
    ),
    # The method's qualname names it: "orphan_method" was no value at all.
    "method_outside_class": Case(
        "orphan_method",
        {},
        "method_outside_class",
        {"qualname": "dump"},
        "target",
        "dump",
        None,
        "does_not_have on a method body needs a method of a class; "
        "'dump' is in none",
    ),
    "signature_mode_requires_method_body": Case(
        "class",
        {"name": "x", "member_kind": "method", "signature_mode": "Compatible"},
        "signature_mode_requires_method_body",
        {"signature_mode": "compatible"},
        "signature_mode",
        "compatible",
        ["any"],
        "signature_mode != 'any' requires the declaration to be on a method body",
    ),
    # A missing name is its own issue, not the one of a malformed name.
    "missing_name": Case(
        "class",
        {"member_kind": "attribute"},
        "missing_name",
        {},
        "name",
        None,
        None,
        "name is required when name_match='exact'",
    ),
    "invalid_severity": Case(
        "class",
        {"name": "x", "severity": "fatal"},
        "invalid_severity",
        {
            "param": "severity",
            "value": "fatal",
            "valid": sorted(_SEVERITIES),
            "reason": "severity must be one of: error, warning, info",
        },
        "severity",
        "fatal",
        _SEVERITIES,
        "severity must be one of: error, warning, info",
    ),
}

ALL_ISSUES = {
    "compiler_invalid_surface",
    "compiler_invalid_target",
    "invalid_name",
    "invalid_member_kind",
    "invalid_storage",
    "invalid_storage_for_member_kind",
    "invalid_name_match",
    "invalid_aliases",
    "invalid_pattern",
    "aliases_not_allowed_for_exact_name_match",
    "pattern_not_allowed_for_exact_name_match",
    "missing_aliases",
    "pattern_not_allowed_for_alias_name_match",
    "aliases_not_allowed_for_regex_name_match",
    "missing_pattern",
    "invalid_signature_mode",
    "invalid_signature_mode_for_member_kind",
    "invalid_include_descriptors",
    "invalid_include_dynamic_attributes",
    "include_descriptors_not_supported_for_method_kind",
    "include_dynamic_attributes_not_supported_for_method_kind",
    "invalid_member_kind_for_method_body",
    "method_outside_class",
    "signature_mode_requires_method_body",
    "missing_name",
    "invalid_severity",
}


def _compile(
    entity_key: str, params: dict[str, Any], surface: str = "body"
) -> tuple[Entity, DeclarationEntry, Any, Any, Any]:
    """Compile ``params`` on the named entity with the suffix ``_SUFFIX``."""
    entity = _entities()[entity_key]
    declaration = DeclarationEntry(
        kind="does_not_have", params=params, lineno=11, col=4, surface=surface
    )
    rules, evidence, results = compile_does_not_have(
        entity, declaration, Mock(), rule_id_suffix=_SUFFIX
    )
    return entity, declaration, rules, evidence, results


def _fix_hint(valid: list[Any] | None, reason: str) -> str:
    """The fix hint a sentinel rule carries for ``valid`` and ``reason``."""
    if valid:
        return f"Use one of: {', '.join(sorted(str(item) for item in valid))}"
    return reason


def test_the_cases_cover_every_issue_the_compiler_reports() -> None:
    """Every issue string in the compiler has at least one case below."""
    assert {case.issue for case in ISSUE_CASES.values()} == ALL_ISSUES


@pytest.mark.parametrize("case", ISSUE_CASES.values(), ids=list(ISSUE_CASES))
def test_dropped_declaration_reports_the_full_sentinel_and_evidence(
    case: Case,
) -> None:
    """A dropped declaration yields one sentinel and one evidence, in full."""
    entity, declaration, rules, evidence, results = _compile(
        case.entity, case.params, case.surface
    )

    assert results == []
    assert len(rules) == 1
    sentinel = rules[0]
    assert sentinel.rule_id == f"{_SENTINEL_PREFIX}/{case.param}{_SUFFIX}"
    assert sentinel.rule_type == "compiler_invalid_param"
    assert sentinel.name == "does_not_have"
    assert sentinel.severity == "error"
    assert sentinel.scope == entity.kind
    assert sentinel.selector.source_entity_id == entity.canonical_id
    assert sentinel.selector.explicit_target is None
    assert sentinel.fix_hints == (_fix_hint(case.valid, case.reason),)
    expected_params = {
        "decorator": "does_not_have",
        "param": case.param,
        "value": case.value,
        "valid": list(case.valid) if case.valid is not None else [],
        "compiler_reason": case.reason,
        "fail_on_unmatched": True,
    }
    assert sentinel.params == expected_params
    assert list(sentinel.params) == list(expected_params)
    assert type(sentinel.params["value"]) is type(case.value)

    assert len(evidence) == 1
    item = evidence[0]
    expected_payload = {"declaration": "does_not_have", "issue": case.issue}
    expected_payload.update(case.payload_extra)
    assert item.type == case.evidence_type
    assert item.source == "compiler"
    assert item.role == "source"
    assert item.entity_id == entity.canonical_id
    assert item.payload == expected_payload
    assert list(item.payload) == sorted(expected_payload)
    assert item.evidence_id == evidence_id(case.evidence_type, expected_payload)
    assert item.location == {
        "filepath": entity.filepath_rel,
        "lineno": declaration.lineno,
        "col": declaration.col,
    }


def test_evidence_falls_back_to_the_entity_line() -> None:
    """A declaration without a line is located at its entity's line."""
    entity = _entities()["class"]
    declaration = DeclarationEntry(kind="does_not_have", params={"name": 3})

    _, evidence, _ = compile_does_not_have(entity, declaration, Mock())

    assert evidence[0].location == {
        "filepath": entity.filepath_rel,
        "lineno": entity.lineno,
        "col": 0,
    }


# Each declaration is wrong in two (or more) ways; the issue is the one the
# compiler checks first.
FIRST_PROBLEM_CASES: dict[str, tuple[str, dict[str, Any], str, str]] = {
    "surface_before_target": (
        "function",
        {"name": 3},
        "signature",
        "compiler_invalid_surface",
    ),
    "target_before_name": ("function", {"name": 3}, "body", "compiler_invalid_target"),
    "name_before_member_kind": (
        "class",
        {"name": "", "member_kind": "field"},
        "body",
        "invalid_name",
    ),
    "member_kind_before_storage": (
        "class",
        {"name": "x", "member_kind": "field", "storage": "slot"},
        "body",
        "invalid_member_kind",
    ),
    "storage_before_name_match": (
        "class",
        {"name": "x", "storage": "slot", "name_match": "glob"},
        "body",
        "invalid_storage",
    ),
    "storage_for_kind_before_name_match": (
        "class",
        {"name": "x", "member_kind": "method", "storage": "class", "name_match": "?"},
        "body",
        "invalid_storage_for_member_kind",
    ),
    "name_match_before_aliases": (
        "class",
        {"name": "x", "name_match": "glob", "aliases": "a"},
        "body",
        "invalid_name_match",
    ),
    "aliases_before_pattern": (
        "class",
        {"name": "x", "aliases": 1, "pattern": 2},
        "body",
        "invalid_aliases",
    ),
    "pattern_type_before_exact_aliases": (
        "class",
        {"name": "x", "aliases": ["a"], "pattern": 2},
        "body",
        "invalid_pattern",
    ),
    "exact_aliases_before_exact_pattern": (
        "class",
        {"name": "x", "aliases": ["a"], "pattern": "p"},
        "body",
        "aliases_not_allowed_for_exact_name_match",
    ),
    "missing_aliases_before_alias_pattern": (
        "class",
        {"name_match": "alias", "pattern": "p"},
        "body",
        "missing_aliases",
    ),
    "regex_aliases_before_missing_pattern": (
        "class",
        {"name_match": "regex", "aliases": ["a"]},
        "body",
        "aliases_not_allowed_for_regex_name_match",
    ),
    "missing_pattern_before_signature_mode": (
        "class",
        {"name_match": "regex", "pattern": "", "signature_mode": "loose"},
        "body",
        "missing_pattern",
    ),
    "regex_before_signature_mode": (
        "class",
        {"name_match": "regex", "pattern": "(", "signature_mode": "loose"},
        "body",
        "invalid_pattern",
    ),
    "signature_mode_before_descriptors": (
        "class",
        {
            "name": "x",
            "member_kind": "method",
            "signature_mode": "loose",
            "include_descriptors": True,
        },
        "body",
        "invalid_signature_mode",
    ),
    "signature_mode_for_kind_before_method_body_kind": (
        "method",
        {"member_kind": "attribute", "signature_mode": "exact"},
        "body",
        "invalid_signature_mode_for_member_kind",
    ),
    "descriptors_before_dynamic_attributes": (
        "method",
        {
            "member_kind": "method",
            "include_descriptors": True,
            "include_dynamic_attributes": True,
        },
        "body",
        "include_descriptors_not_supported_for_method_kind",
    ),
    "dynamic_attributes_before_method_body": (
        "class",
        {
            "name": "x",
            "member_kind": "method",
            "include_dynamic_attributes": True,
            "signature_mode": "exact",
        },
        "body",
        "include_dynamic_attributes_not_supported_for_method_kind",
    ),
    "method_body_kind_before_orphan": (
        "orphan_method",
        {"member_kind": "property"},
        "body",
        "invalid_member_kind_for_method_body",
    ),
    "include_type_before_method_kind": (
        "class",
        {"name": "x", "member_kind": "method", "include_descriptors": "yes"},
        "body",
        "invalid_include_descriptors",
    ),
    "missing_name_before_severity": (
        "class",
        {"member_kind": "attribute", "severity": "fatal"},
        "body",
        "missing_name",
    ),
    "class_before_severity": (
        "orphan_method",
        {"severity": "fatal"},
        "body",
        "method_outside_class",
    ),
    "signature_mode_on_class_before_missing_name": (
        "class",
        {"signature_mode": "exact"},
        "body",
        "signature_mode_requires_method_body",
    ),
}


@pytest.mark.parametrize(
    ("entity_key", "params", "surface", "issue"),
    FIRST_PROBLEM_CASES.values(),
    ids=list(FIRST_PROBLEM_CASES),
)
def test_only_the_first_problem_is_reported(
    entity_key: str, params: dict[str, Any], surface: str, issue: str
) -> None:
    """With several problems, only the first checked one is reported."""
    _, _, rules, evidence, _ = _compile(entity_key, params, surface)

    assert [rule.rule_type for rule in rules] == ["compiler_invalid_param"]
    assert [item.payload["issue"] for item in evidence] == [issue]


def test_method_body_rule_keeps_its_parameters_in_order() -> None:
    """A valid method-body declaration compiles to a v2 rule on its class."""
    entities = _entities()
    entity, _, rules, evidence, results = _compile(
        "method",
        {
            "name_match": "REGEX",
            "pattern": " ^dump$ ",
            "signature_mode": "Exact",
            "severity": "WARNING",
        },
    )

    assert evidence == []
    assert results == []
    assert len(rules) == 1
    rule = rules[0]
    assert rule.rule_id == f"NEG001/does_not_have/v2{_SUFFIX}"
    assert rule.rule_type == "member_absence"
    assert rule.severity == "warning"
    assert rule.scope == "class"
    assert rule.selector.source_entity_id == entities["class"].canonical_id
    assert list(rule.params.items()) == [
        ("name", "dump"),
        ("member_kind", "any"),
        ("storage", "any"),
        ("declared_only", False),
        ("fail_on_unmatched", False),
        ("name_match", "regex"),
        ("aliases", None),
        ("pattern", "^dump$"),
        ("signature_mode", "exact"),
        ("include_descriptors", False),
        ("include_dynamic_attributes", False),
        ("signature_anchor_entity_id", entity.canonical_id),
    ]


def test_v1_class_rule_keeps_its_parameters_in_order() -> None:
    """A class declaration with only v1 parameters compiles to a v1 rule."""
    entity, _, rules, evidence, _ = _compile(
        "class",
        {"name": " token ", "member_kind": "Attribute", "declared_only": "yes"},
    )

    assert evidence == []
    rule = rules[0]
    assert rule.rule_id == f"NEG001/does_not_have/v1{_SUFFIX}"
    assert rule.scope == "class"
    assert rule.severity == "error"
    assert rule.selector.source_entity_id == entity.canonical_id
    assert list(rule.params.items()) == [
        ("name", "token"),
        ("member_kind", "attribute"),
        ("storage", "any"),
        ("declared_only", True),
        ("fail_on_unmatched", False),
    ]


_DEFAULTED = [
    "member_kind",
    "storage",
    "name_match",
    "signature_mode",
    "include_descriptors",
    "include_dynamic_attributes",
    "declared_only",
    "aliases",
    "pattern",
    "severity",
]


@pytest.mark.parametrize("param", _DEFAULTED)
def test_an_explicit_none_is_the_default(param: str) -> None:
    """``param=None`` compiles as if the parameter were not given."""
    _, _, absent, absent_evidence, _ = _compile("class", {"name": "x"})
    _, _, rules, evidence, _ = _compile("class", {"name": "x", param: None})

    assert absent_evidence == evidence == []
    assert [rule.rule_id for rule in rules] == [rule.rule_id for rule in absent]
    assert rules[0].params == absent[0].params
    assert rules[0].severity == absent[0].severity == "error"


@pytest.mark.parametrize("value", [True, False])
@pytest.mark.parametrize(
    "option", ["include_descriptors", "include_dynamic_attributes"]
)
def test_an_include_option_takes_a_bool(option: str, value: bool) -> None:
    """A bool is kept as it is, in the v2 parameters of the rule."""
    _, _, rules, evidence, _ = _compile(
        "class", {"name": "x", "member_kind": "attribute", option: value}
    )

    assert evidence == []
    assert rules[0].params[option] is value
