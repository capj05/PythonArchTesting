from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

import pytest

from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.rules.compilation import compile_rules
from pythonarchtesting.rules.compilation.decorators.runtime_structure import (
    _required_positional,
)

_PROTOCOL = """
from typing import Annotated, Protocol
from pythonarchtesting.rules import implements_runtime_protocol

class Exporter(Protocol):
    name: str
    separator: str = ","

    def export(self, rows, header=None): ...

    @staticmethod
    def build(kind, options): ...

    @classmethod
    def create(cls, kind): ...

    @property
    def label(self) -> str: ...

    def flush(self): ...

    def split(self, value, /, size, *rest, strict, **extra): ...

class Plain:
    pass
"""


def _entities(source: str) -> list:
    return extract_entities_from_source(
        textwrap.dedent(source).strip() + "\n",
        Path("source_module.py"),
        Path("."),
        None,
        role="source",
        include_nested_functions=False,
        root_label="source",
    )


def _compile(marker: str, *, on: str = "class") -> tuple[list, list, list]:
    holder = (
        f"class CsvExporter:\n    __archtest__: Annotated[None, {marker}]\n"
        if on == "class"
        else f"def export():\n    __archtest__: Annotated[None, {marker}]\n"
    )
    entities = _entities(_PROTOCOL + "\n" + holder)
    return compile_rules(entities, Mock())


def test_protocol_members_are_stored_with_their_positional_arity() -> None:
    rules, evidence, _ = _compile(
        'implements_runtime_protocol(Exporter, cases=[{"args": [";"]}])'
    )

    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["DYN007/implements_runtime_protocol/v1"]
    rule = rules[0]
    assert rule.rule_type == "runtime_protocol"
    assert rule.scope == "class"
    assert rule.params["protocol"] == "source_module.Exporter"
    assert rule.params["methods"] == {
        "build": 2,
        "create": 1,
        "export": 1,
        "flush": 0,
        "split": 2,
    }
    assert rule.params["attributes"] == ["label", "name", "separator"]
    assert rule.params["cases"] == [{"args": [";"]}]


def test_a_function_is_not_a_valid_target() -> None:
    rules, evidence, _ = _compile(
        "implements_runtime_protocol(Exporter, cases=[{}])", on="function"
    )

    # The misplaced marker is a FAILED sentinel, not missing from the report.
    assert [(rule.rule_type, rule.params["param"]) for rule in rules] == [
        ("compiler_invalid_param", "target_kind")
    ]
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


@pytest.mark.parametrize(
    ("protocol", "reason"),
    [("Missing", None), ("Plain", "not_typing_protocol")],
)
def test_an_unusable_protocol_yields_evidence_and_a_sentinel(
    protocol: str, reason: str | None
) -> None:
    rules, evidence, _ = _compile(
        f"implements_runtime_protocol({protocol}, cases=[{{}}])"
    )

    assert [rule.rule_type for rule in rules] == ["compiler_invalid_param"]
    assert [item.type for item in evidence] == ["compiler_invalid_protocol_reference"]
    assert evidence[0].payload["declaration"] == "implements_runtime_protocol"
    if reason is not None:
        assert evidence[0].payload["reason"] == reason


@pytest.mark.parametrize(
    ("marker", "reason"),
    [
        ("implements_runtime_protocol(Exporter, cases=[])", "non-empty list"),
        (
            'implements_runtime_protocol(Exporter, cases=[{"returns": 1}])',
            "unknown keys: returns",
        ),
    ],
)
def test_invalid_cases_compile_to_a_sentinel(marker: str, reason: str) -> None:
    rules, evidence, _ = _compile(marker)

    assert [rule.rule_type for rule in rules] == ["compiler_invalid_param"]
    assert rules[0].params["param"] == "cases"
    assert reason in rules[0].params["compiler_reason"]
    assert rules[0].rule_id.startswith("DYN007/implements_runtime_protocol/")
    assert [item.type for item in evidence] == ["compiler_invalid_param"]


def _method(name: str):
    return next(e for e in _entities(_PROTOCOL) if e.name == name)


@pytest.mark.parametrize(
    ("name", "required"),
    [("export", 1), ("build", 2), ("create", 1), ("flush", 0), ("split", 2)],
)
def test_required_positional_counts_without_self_or_defaults(
    name: str, required: int
) -> None:
    assert _required_positional(_method(name)) == required


def test_required_positional_of_an_entity_without_a_signature_is_zero() -> None:
    assert _required_positional(_method("Plain")) == 0
