from __future__ import annotations

from unittest.mock import Mock

from pythonarchtesting.rules.compilation import compile_rules
from tests.unit.test_rules.protocol_rule_test_helpers import (
    extract_entities,
    extract_entity,
)


def test_api004_classmethod_compiles_to_required_factory_rule() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyFactory:
    @classmethod
    def create(cls, name: str):
        __archtest__: Annotated[None, required_factory()]
        return cls()
"""
    source_entity = extract_entity(source, role="source", kind="method", name="create")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API004/required_factory/v1"]
    assert [rule.rule_type for rule in rules] == ["api_signature"]


def test_api004_init_source_compiles() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyService:
    def __init__(self, name: str, value: int):
        __archtest__: Annotated[None, required_factory()]
        self.name = name
        self.value = value
"""
    source_entity = extract_entity(
        source, role="source", kind="method", name="__init__"
    )
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API004/required_factory/v1"]


def test_api004_non_method_placement_emits_compiler_invalid_target_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyClass:
    __archtest__: Annotated[None, required_factory()]
"""
    source_entities = extract_entities(source, role="source")
    class_entity = next(entity for entity in source_entities if entity.kind == "class")
    rules, evidence, compiler_results = compile_rules([class_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


def test_api004_plain_instance_method_emits_compiler_invalid_source_method_evidence() -> (
    None
):
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyClass:
    def my_method(self, x: int):
        __archtest__: Annotated[None, required_factory()]
        return x
"""
    source_entity = extract_entity(
        source, role="source", kind="method", name="my_method"
    )
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_source_method"]


def test_api004_invalid_satisfy_with_emits_compiler_invalid_param_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyFactory:
    @classmethod
    def create(cls):
        __archtest__: Annotated[None, required_factory(satisfy_with=("unknown_kind",))]
        return cls()
"""
    source_entity = extract_entity(source, role="source", kind="method", name="create")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_param"]


def test_api004_name_match_alias_without_aliases_emits_compiler_invalid_param() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyFactory:
    @classmethod
    def create(cls, name: str):
        __archtest__: Annotated[None, required_factory(name_match="alias")]
        return cls()
"""
    source_entity = extract_entity(source, role="source", kind="method", name="create")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_param"]


def test_api004_multiple_factory_rules_on_same_entity_get_suffixed_rule_ids() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyFactory:
    @classmethod
    def create(cls, name: str):
        __archtest__: Annotated[None, required_factory(satisfy_with=("constructor",))]
        __archtest__: Annotated[None, required_factory(satisfy_with=("classmethod",))]
        return cls()
"""
    source_entity = extract_entity(source, role="source", kind="method", name="create")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == [
        "API004/required_factory/v1/d0",
        "API004/required_factory/v1/d1",
    ]


def test_api004_params_survive_compilation() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_factory

class MyFactory:
    @classmethod
    def create(cls, name: str):
        __archtest__: Annotated[
            None,
            required_factory(
                signature_mode="exact",
                satisfy_with=("constructor",),
                allow_inherited=False,
                name_match="exact",
            ),
        ]
        return cls()
"""
    source_entity = extract_entity(source, role="source", kind="method", name="create")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert len(rules) == 1
    assert rules[0].params["mode"] == "exact"
    assert rules[0].params["satisfy_with"] == ["constructor"]
    assert rules[0].params["allow_inherited"] is False
    assert rules[0].params["name_match"] == "exact"
