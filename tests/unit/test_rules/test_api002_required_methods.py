from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchResult, MatchStatus
from pythonarchtesting.rules.compilation import compile_rules


def _extract_entity(
    source_text: str,
    *,
    role: str,
    kind: str,
    name: str,
) -> Entity:
    entities = extract_entities_from_source(
        source_text=source_text,
        file_path=Path(f"{role}_module.py"),
        root_path=Path("."),
        target_module_name=None,
        role=role,  # type: ignore[arg-type]
        include_nested_functions=False,
        root_label=role,
    )
    for entity in entities:
        if entity.kind == kind and entity.name == name:
            return entity
    raise AssertionError(f"Entity '{name}' ({kind}) not found for role={role}")


def test_api002_compile_emits_required_method_rule():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method()]
        return data
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API002/required_method/v1"]
    assert [rule.rule_type for rule in rules] == ["api_signature"]
    assert rules[0].params["enforce_method_kind"] is True
    assert rules[0].params["fail_on_unmatched"] is True


def test_api002_compile_emits_required_method_rule_from_annotation() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method(signature_mode="compatible")]
        return data
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert compiler_results == []
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["API002/required_method/v1"]
    assert [rule.rule_type for rule in rules] == ["api_signature"]
    assert rules[0].params["enforce_method_kind"] is True
    assert rules[0].params["fail_on_unmatched"] is True


def test_api002_evaluation_passes_for_compatible_method():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    @classmethod
    def from_path(cls, path: str) -> "Processor":
        __archtest__: Annotated[
            None,
            required_method(signature_mode="compatible"),
        ]
        return cls()
"""
    target = """
class Processor:
    @classmethod
    def from_path(cls, path: str) -> "Processor":
        return cls()
"""
    source_entity = _extract_entity(
        source, role="source", kind="method", name="from_path"
    )
    target_entity = _extract_entity(
        target, role="target", kind="method", name="from_path"
    )

    rules, _, _ = compile_rules([source_entity], Mock())
    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([target_entity])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]


def test_api002_evaluation_fails_for_method_kind_mismatch():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    @classmethod
    def from_path(cls, path: str) -> "Processor":
        __archtest__: Annotated[None, required_method()]
        return cls()
"""
    target = """
class Processor:
    def from_path(self, path: str) -> "Processor":
        return self
"""
    source_entity = _extract_entity(
        source, role="source", kind="method", name="from_path"
    )
    target_entity = _extract_entity(
        target, role="target", kind="method", name="from_path"
    )

    rules, _, _ = compile_rules([source_entity], Mock())
    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([target_entity])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "method kind mismatch" in results[0].message


def test_api002_unmatched_required_method_fails():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

class Processor:
    def run(self, data: int) -> int:
        __archtest__: Annotated[None, required_method()]
        return data
"""
    source_entity = _extract_entity(source, role="source", kind="method", name="run")
    rules, _, _ = compile_rules([source_entity], Mock())

    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.UNMATCHED,
            target_id=None,
            confidence=0.2,
            reasons=[],
            candidates=[],
        )
    }

    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert "Required target entity missing or not matchable" in results[0].message


def test_api002_compile_non_method_emits_compiler_evidence():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_method

def run(data: int) -> int:
    __archtest__: Annotated[None, required_method()]
    return data
"""
    source_entity = _extract_entity(source, role="source", kind="function", name="run")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]
