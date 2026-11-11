"""A declaration dropped for an invalid argument value stays in the report.

Each case declares one marker with one invalid argument value. The marker's
compiler drops the declaration with the compiler evidence it has always
reported the problem with, unchanged, and one ``compiler_invalid_param``
sentinel rule for the argument at fault, so the dropped marker shows up as a
FAILED result instead of vanishing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple
from unittest.mock import Mock

import pytest

from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.rules.compilation import compile_rules

_SOURCE = """
from __future__ import annotations

from typing import Annotated, Protocol

from pythonarchtesting.rules import (
    enforce_flow,
    flow,
    forbid_imports,
    implements_protocol,
    implements_runtime_protocol,
    required_attribute,
    required_constructor,
    required_entity_signature,
    required_method,
)


class Port(Protocol):
    def run(self) -> None: ...


class NotAProtocol:
    pass


class Service:
    CLASS

    def __init__(self, value: int) -> None:
        self.value = value

    def run(self) -> None:
        METHOD


def handler(value: int) -> int:
    FUNCTION
    return value


def _architecture_rules_marker() -> None:
    MODULE
    return None
"""

_SITES = ("CLASS", "METHOD", "FUNCTION", "MODULE")


class Case(NamedTuple):
    """Where the declaration is, its text, the sentinel's rule id, and the
    compiler evidence as (type, payload)."""

    site: str
    declaration: str
    rule_id: str
    evidence: list[tuple[str, dict[str, Any]]]


def _compile(site: str, declaration: str) -> tuple[list[Any], list[Any]]:
    source = _SOURCE
    for name in _SITES:
        source = source.replace(name, declaration if name == site else "pass")
    entities = extract_entities_from_source(
        source_text=source,
        file_path=Path("app.py"),
        root_path=Path("."),
        target_module_name=None,
        role="source",
        include_nested_functions=False,
        root_label="source",
    )
    rules, evidence, _ = compile_rules(entities, Mock())
    return rules, evidence


def _marker(text: str) -> str:
    return f"__archtest__: Annotated[None, {text}]"


def _flow(*lines: str) -> str:
    return "\n    ".join(_marker(line) for line in lines)


_API001 = "API001/required_entity_signature/invalid_declaration"
_API002 = "API002/required_method/invalid_declaration"
_API003C = "API003/required_constructor/invalid_declaration"
_API003A = "API003/required_attribute/invalid_declaration"
_DEP001 = "DEP001/forbid_imports/invalid_declaration"
_FLW001 = "FLW001/enforce_flow/invalid_declaration"
_FLW002 = "FLW002/enforce_flow_runtime/invalid_declaration"


def _method(params: dict[str, Any], reason: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        (
            "compiler_invalid_declaration",
            {
                "decorator": "required_method",
                "issue": "compiler_invalid_declaration",
                "params": params,
                "reason": reason,
            },
        )
    ]


def _constructor(params: dict[str, Any], reason: str) -> list[tuple[str, Any]]:
    return [
        (
            "compiler_invalid_declaration",
            {
                "decorator": "required_constructor",
                "issue": "compiler_invalid_declaration",
                "params": params,
                "reason": reason,
            },
        )
    ]


def _attribute(issue: str, **payload: Any) -> list[tuple[str, dict[str, Any]]]:
    return [
        (
            "compiler_invalid_attribute_declaration",
            {"declaration": "required_attribute", "issue": issue, **payload},
        )
    ]


def _flow_evidence(
    issue: str, declaration: str = "enforce_flow", **payload: Any
) -> list[tuple[str, dict[str, Any]]]:
    return [
        (
            "compiler_invalid_flow_declaration",
            {"declaration": declaration, "issue": issue, **payload},
        )
    ]


def _protocol(marker: str, name: str, reason: str) -> list[tuple[str, Any]]:
    return [
        (
            "compiler_invalid_protocol_reference",
            {
                "declaration": marker,
                "issue": "compiler_invalid_protocol_reference",
                "normalized": f"app.{name}",
                "protocol": name,
                "reason": reason,
            },
        )
    ]


CASES: dict[str, Case] = {
    "signature_return_annotation": Case(
        "FUNCTION",
        _marker('required_entity_signature(return_annotation="bogus")'),
        f"{_API001}/return_annotation",
        [
            (
                "compiler_invalid_param",
                {
                    "decorator": "required_entity_signature",
                    "issue": "compiler_invalid_param",
                    "param": "return_annotation",
                    "valid": ["error", "ignore", "off", "warning"],
                    "value": "bogus",
                },
            )
        ],
    ),
    "method_name_match": Case(
        "METHOD",
        _marker('required_method(name_match="bogus")'),
        f"{_API002}/name_match",
        _method(
            {"name_match": "bogus"},
            "name_match must be one of: exact, alias, regex, any",
        ),
    ),
    "method_aliases_not_list": Case(
        "METHOD",
        _marker('required_method(name_match="alias", aliases="x")'),
        f"{_API002}/aliases",
        _method(
            {"aliases": "x", "name_match": "alias"},
            "aliases must be a list of non-empty strings",
        ),
    ),
    "method_aliases_blank": Case(
        "METHOD",
        _marker('required_method(name_match="alias", aliases=[" "])'),
        f"{_API002}/aliases",
        _method(
            {"aliases": [" "], "name_match": "alias"},
            "aliases must contain only non-empty strings",
        ),
    ),
    "method_pattern_not_text": Case(
        "METHOD",
        _marker('required_method(name_match="regex", pattern=3)'),
        f"{_API002}/pattern",
        _method(
            {"name_match": "regex", "pattern": 3},
            "pattern must be a non-empty string",
        ),
    ),
    "method_exact_with_aliases": Case(
        "METHOD",
        _marker('required_method(aliases=["x"])'),
        f"{_API002}/aliases",
        _method(
            {"aliases": ["x"]},
            "exact name matching does not accept aliases or pattern",
        ),
    ),
    "method_exact_with_pattern": Case(
        "METHOD",
        _marker('required_method(pattern="x")'),
        f"{_API002}/pattern",
        _method(
            {"pattern": "x"},
            "exact name matching does not accept aliases or pattern",
        ),
    ),
    "method_alias_without_aliases": Case(
        "METHOD",
        _marker('required_method(name_match="alias")'),
        f"{_API002}/aliases",
        _method(
            {"name_match": "alias"},
            "alias name matching requires a non-empty aliases list",
        ),
    ),
    "method_alias_with_pattern": Case(
        "METHOD",
        _marker('required_method(name_match="alias", aliases=["x"], pattern="x")'),
        f"{_API002}/pattern",
        _method(
            {"aliases": ["x"], "name_match": "alias", "pattern": "x"},
            "alias name matching does not accept pattern",
        ),
    ),
    "method_regex_with_aliases": Case(
        "METHOD",
        _marker('required_method(name_match="regex", aliases=["x"], pattern="x")'),
        f"{_API002}/aliases",
        _method(
            {"aliases": ["x"], "name_match": "regex", "pattern": "x"},
            "regex name matching does not accept aliases",
        ),
    ),
    "method_regex_without_pattern": Case(
        "METHOD",
        _marker('required_method(name_match="regex")'),
        f"{_API002}/pattern",
        _method(
            {"name_match": "regex"},
            "regex name matching requires a non-empty pattern",
        ),
    ),
    "method_regex_invalid": Case(
        "METHOD",
        _marker('required_method(name_match="regex", pattern="(")'),
        f"{_API002}/pattern",
        _method(
            {"name_match": "regex", "pattern": "("},
            "invalid regex pattern: missing ), unterminated subpattern at position 0",
        ),
    ),
    "method_any_with_pattern": Case(
        "METHOD",
        _marker('required_method(name_match="any", pattern="x")'),
        f"{_API002}/pattern",
        _method(
            {"name_match": "any", "pattern": "x"},
            "any name matching does not accept aliases or pattern",
        ),
    ),
    "imports_mode": Case(
        "MODULE",
        _marker('forbid_imports("x", mode="bogus")'),
        f"{_DEP001}/mode",
        [
            (
                "compiler_invalid_import_policy_mode",
                {
                    "allowed_values": ["direct", "reachable"],
                    "declaration": "forbid_imports",
                    "issue": "invalid_mode",
                    "message": "forbid_imports mode must be 'reachable' or 'direct'.",
                    "mode": "bogus",
                    "severity": "error",
                },
            )
        ],
    ),
    "constructor_signature_mode": Case(
        "CLASS",
        _marker('required_constructor(signature_mode="bogus")'),
        f"{_API003C}/signature_mode",
        _constructor(
            {"signature_mode": "bogus"},
            "signature_mode must be one of: compatible, exact, any",
        ),
    ),
    "constructor_kind": Case(
        "CLASS",
        _marker('required_constructor(constructor_kind="bogus")'),
        f"{_API003C}/constructor_kind",
        _constructor(
            {"constructor_kind": "bogus"},
            "constructor_kind must be one of: auto, __init__, __new__",
        ),
    ),
    "attribute_name": Case(
        "CLASS",
        _marker('required_attribute("")'),
        f"{_API003A}/name",
        _attribute("invalid_name", name=""),
    ),
    "attribute_storage": Case(
        "CLASS",
        _marker('required_attribute("value", storage="bogus")'),
        f"{_API003A}/storage",
        _attribute("invalid_storage", storage="bogus"),
    ),
    "attribute_descriptor_kinds": Case(
        "CLASS",
        _marker('required_attribute("value", descriptor_kinds="x")'),
        f"{_API003A}/descriptor_kinds",
        _attribute("invalid_descriptor_kinds", descriptor_kinds="x"),
    ),
    "attribute_unsupported_descriptor_kind": Case(
        "CLASS",
        _marker('required_attribute("value", descriptor_kinds=("bogus",))'),
        f"{_API003A}/descriptor_kinds",
        _attribute(
            "unsupported_descriptor_kind",
            descriptor_kinds=["bogus"],
            unsupported_descriptor_kinds=["bogus"],
        ),
    ),
    "attribute_property_with_class_storage": Case(
        "CLASS",
        _marker('required_attribute("value", allow_property=True, storage="class")'),
        f"{_API003A}/allow_property",
        _attribute(
            "property_incompatible_with_class_storage",
            allow_property=True,
            storage="class",
        ),
    ),
    "flow_stages": Case(
        "FUNCTION",
        _flow("enforce_flow([])"),
        f"{_FLW001}/stages",
        _flow_evidence("invalid_stages", stages=[]),
    ),
    "flow_runtime_stages": Case(
        "FUNCTION",
        _flow("enforce_flow([], cases=[{}])"),
        f"{_FLW002}/stages",
        _flow_evidence("invalid_stages", stages=[]),
    ),
    "flow_ambiguous_variable": Case(
        "FUNCTION",
        _flow(
            'flow("raw", variable="a")',
            'flow("raw", variable="b")',
            'enforce_flow(["raw"])',
        ),
        f"{_FLW001}/variable",
        _flow_evidence("ambiguous_variable", variables=["a", "b"]),
    ),
    "flow_invalid_variable": Case(
        "FUNCTION",
        _flow('flow("raw")', 'enforce_flow(["raw"], variable=3)'),
        f"{_FLW001}/variable",
        _flow_evidence("invalid_variable", variable=3),
    ),
    "flow_invalid_stage": Case(
        "FUNCTION",
        _flow('flow(" ", variable="v")', 'enforce_flow(["raw"], variable="v")'),
        f"{_FLW001}/stage",
        _flow_evidence("invalid_stage", declaration="flow", stage=" "),
    ),
    "protocol_missing": Case(
        "CLASS",
        _marker("implements_protocol(Missing)"),
        "PRO001/implements_protocol/invalid_declaration/protocol",
        _protocol("implements_protocol", "Missing", "ambiguous_or_missing"),
    ),
    "protocol_not_a_protocol": Case(
        "CLASS",
        _marker("implements_protocol(NotAProtocol)"),
        "PRO001/implements_protocol/invalid_declaration/protocol",
        _protocol("implements_protocol", "NotAProtocol", "not_typing_protocol"),
    ),
    "runtime_protocol_missing": Case(
        "CLASS",
        _marker("implements_runtime_protocol(Missing, cases=[{}])"),
        "DYN007/implements_runtime_protocol/invalid_declaration/protocol",
        _protocol("implements_runtime_protocol", "Missing", "ambiguous_or_missing"),
    ),
}


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_an_invalid_argument_value_gives_one_sentinel(case: Case) -> None:
    rules, evidence = _compile(case.site, case.declaration)

    assert [(rule.rule_id, rule.rule_type) for rule in rules] == [
        (case.rule_id, "compiler_invalid_param")
    ]
    sentinel = rules[0]
    assert sentinel.severity == "error"
    assert sentinel.params["param"] == case.rule_id.rsplit("/", 1)[1]
    assert sentinel.params["compiler_reason"]
    assert [(item.type, item.payload) for item in evidence] == case.evidence


_INDENT = {"CLASS": 4, "METHOD": 8, "FUNCTION": 4, "MODULE": 4}


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_the_sentinel_carries_the_rule_id_suffix(case: Case) -> None:
    """Two declarations of the marker on one entity keep two sentinels apart;
    the second differs in its severity, so it is not the same declaration."""
    if "flow(" in case.declaration:
        pytest.skip("a second enforce_flow would share the flow markers")
    newline = "\n" + " " * _INDENT[case.site]
    second = case.declaration.replace(")]", ', severity="warning")]')
    rules, _ = _compile(case.site, case.declaration + newline + second)

    assert [rule.rule_id for rule in rules] == [
        f"{case.rule_id}/d0",
        f"{case.rule_id}/d1",
    ]
