from __future__ import annotations

from unittest.mock import Mock

from pythonarchtesting.rules.compilation import compile_rules
from tests.unit.test_rules.protocol_rule_test_helpers import extract_entities


def test_api003_compile_emits_required_constructor_rule() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[None, required_constructor()]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API003/required_constructor/v1"]
    assert [rule.rule_type for rule in rules] == ["api_signature"]
    params = rules[0].params
    assert params["mode"] == "compatible"
    assert params["constructor_kind"] == "auto"
    assert params["resolved_constructor_kind"] == "__init__"
    assert params["allow_inherited"] is True
    assert params["allow_missing"] is False
    assert params["enforce_method_kind"] is False
    assert params["check_return"] is False
    assert params["fail_on_unmatched"] is True
    assert params["allow_extra_params"] is True
    assert params["allow_param_rename"] is False
    assert isinstance(params["expected_source_constructor_id"], str)


def test_api003_compile_auto_falls_back_to_new_when_no_init() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class Tuple2:
    __archtest__: Annotated[None, required_constructor()]

    def __new__(cls, a: int, b: int) -> "Tuple2":
        return super().__new__(cls)
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API003/required_constructor/v1"]
    assert rules[0].params["constructor_kind"] == "auto"
    assert rules[0].params["resolved_constructor_kind"] == "__new__"


def test_api003_compile_explicit_new_targets_new() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class Singleton:
    __archtest__: Annotated[
        None, required_constructor(constructor_kind="__new__")
    ]

    def __init__(self) -> None:
        pass

    def __new__(cls) -> "Singleton":
        return super().__new__(cls)
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert rules[0].params["constructor_kind"] == "__new__"
    assert rules[0].params["resolved_constructor_kind"] == "__new__"


def test_api003_compile_invalid_kind_emits_compiler_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[
        None, required_constructor(constructor_kind="__call__")
    ]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]
    assert evidence[0].payload["decorator"] == "required_constructor"


def test_api003_compile_non_class_placement_emits_invalid_target() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

def build() -> None:
    __archtest__: Annotated[None, required_constructor()]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


def test_api003_compile_missing_source_constructor_emits_compiler_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class Bare:
    __archtest__: Annotated[None, required_constructor()]
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]
    assert "no declared constructor" in evidence[0].payload["reason"]


def test_api003_compile_severity_passthrough() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[
        None, required_constructor(severity="warning")
    ]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert rules[0].severity == "warning"


def test_api003_compile_threads_allow_missing_flag() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[
        None, required_constructor(allow_missing=True)
    ]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert len(rules) == 1
    assert rules[0].params["allow_missing"] is True
    assert rules[0].params["fail_on_unmatched"] is False


def test_api003_compile_invalid_allow_missing_emits_compiler_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class User:
    __archtest__: Annotated[
        None, required_constructor(allow_missing="yes")
    ]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_declaration"]
    assert evidence[0].payload["decorator"] == "required_constructor"
    assert "allow_missing must be a boolean" in evidence[0].payload["reason"]


def test_api003_compile_multiple_required_constructors_dedupe_and_suffix() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_constructor

class Dual:
    __archtest__: Annotated[None, required_constructor(signature_mode="compatible")]
    __archtest__: Annotated[None, required_constructor(signature_mode="exact")]

    def __init__(self, name: str) -> None:
        self.name = name
"""
    source_entities = extract_entities(source, role="source")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == [
        "API003/required_constructor/v1/d0",
        "API003/required_constructor/v1/d1",
    ]
    assert rules[0].params["mode"] == "compatible"
    assert rules[1].params["mode"] == "exact"
