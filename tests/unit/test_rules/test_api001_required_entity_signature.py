from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchResult, MatchStatus
from pythonarchtesting.rules.compilation import compile_rules


def _extract_entities(source_text: str, *, role: str) -> list[Entity]:
    return extract_entities_from_source(
        source_text=source_text,
        file_path=Path(f"{role}_module.py"),
        root_path=Path("."),
        target_module_name=None,
        role=role,  # type: ignore[arg-type]
        include_nested_functions=False,
        root_label=role,
    )


def _extract_function_entity(source_text: str, *, role: str, name: str) -> Entity:
    entities = _extract_entities(source_text, role=role)
    for entity in entities:
        if entity.kind == "function" and entity.name == name:
            return entity
    raise AssertionError(f"Function '{name}' not found for role={role}")


def test_api001_compile_emits_signature_and_return_rules():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_entity_signature

def normalize(a: int, b: int = 0) -> int:
    __archtest__: Annotated[None, required_entity_signature()]
    return a + b
"""
    source_entity = _extract_function_entity(source, role="source", name="normalize")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == [
        "API001/required_entity_signature/v1",
        "API001/required_entity_signature_return/v1",
    ]
    assert [rule.rule_type for rule in rules] == ["api_signature", "api_signature"]
    assert rules[0].params["fail_on_unmatched"] is True
    assert rules[1].params["return_only"] is True
    assert rules[1].severity == "warning"


def test_api001_compile_emits_same_rules_from_annotation_declaration():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_entity_signature

def normalize(a: int, b: int = 0) -> int:
    __archtest__: Annotated[
        None,
        required_entity_signature(mode="compatible", return_annotation="warning"),
    ]
    return a + b
"""
    source_entity = _extract_function_entity(source, role="source", name="normalize")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == [
        "API001/required_entity_signature/v1",
        "API001/required_entity_signature_return/v1",
    ]
    assert [rule.rule_type for rule in rules] == ["api_signature", "api_signature"]
    assert rules[0].params["fail_on_unmatched"] is True
    assert rules[1].params["return_only"] is True
    assert rules[1].severity == "warning"


def test_api001_compile_emits_same_rules_from_signature_annotation_declaration():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_entity_signature

def normalize(
    value: str,
) -> Annotated[str, required_entity_signature(mode="compatible", return_annotation="warning")]:
    return value.strip()
"""
    source_entity = _extract_function_entity(source, role="source", name="normalize")
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == [
        "API001/required_entity_signature/v1",
        "API001/required_entity_signature_return/v1",
    ]
    assert [rule.rule_type for rule in rules] == ["api_signature", "api_signature"]
    assert rules[0].params["fail_on_unmatched"] is True
    assert rules[1].params["return_only"] is True
    assert rules[1].severity == "warning"


def test_api001_evaluation_passes_for_compatible_target():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_entity_signature

def normalize(a: int, b: int = 0) -> int:
    __archtest__: Annotated[
        None,
        required_entity_signature(mode="compatible", return_annotation="error"),
    ]
    return a + b
"""
    target = """
def normalize(a: int, b: int = 1) -> int:
    return a + b
"""
    source_entity = _extract_function_entity(source, role="source", name="normalize")
    target_entity = _extract_function_entity(target, role="target", name="normalize")

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
    assert [result.status for result in results] == ["OK", "OK"]


def test_api001_evaluation_fails_for_incompatible_signature():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_entity_signature

def normalize(a: int, b: int) -> int:
    __archtest__: Annotated[
        None,
        required_entity_signature(mode="compatible", return_annotation="off"),
    ]
    return a + b
"""
    target = """
def normalize(a: int) -> int:
    return a
"""
    source_entity = _extract_function_entity(source, role="source", name="normalize")
    target_entity = _extract_function_entity(target, role="target", name="normalize")

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
    assert len(results) == 1
    assert results[0].status == "FAILED"
    assert "missing parameter 'b'" in results[0].message


def test_api001_unmatched_required_entity_fails():
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_entity_signature

def normalize(a: int, b: int) -> int:
    __archtest__: Annotated[
        None,
        required_entity_signature(return_annotation="warning"),
    ]
    return a + b
"""
    source_entity = _extract_function_entity(source, role="source", name="normalize")
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
    assert [result.status for result in results] == ["FAILED", "SKIPPED"]
    assert "Required target entity missing or not matchable" in results[0].message


def test_api001_return_annotation_accepts_optional_union_normalization() -> None:
    source = """
from typing import Annotated, Optional
from pythonarchtesting.rules import required_entity_signature

class Result:
    pass

def build() -> Optional[Result]:
    __archtest__: Annotated[
        None,
        required_entity_signature(return_annotation="error"),
    ]
    raise NotImplementedError
"""
    target = """
class Result:
    pass

def build() -> Result | None:
    return Result()
"""
    source_entity = _extract_function_entity(source, role="source", name="build")
    target_entity = _extract_function_entity(target, role="target", name="build")

    rules, _, _ = compile_rules(_extract_entities(source, role="source"), Mock())
    source_index = build_entity_index(_extract_entities(source, role="source"))
    target_index = build_entity_index(_extract_entities(target, role="target"))
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
    assert [result.status for result in results] == ["OK", "OK"]


def test_api001_return_annotation_accepts_target_subtype() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_entity_signature

class BaseResult:
    pass

def build() -> BaseResult:
    __archtest__: Annotated[
        None,
        required_entity_signature(return_annotation="error"),
    ]
    raise NotImplementedError
"""
    target = """
class BaseResult:
    pass

class ChildResult(BaseResult):
    pass

def build() -> ChildResult:
    return ChildResult()
"""
    source_entities = _extract_entities(source, role="source")
    target_entities = _extract_entities(target, role="target")
    source_entity = _extract_function_entity(source, role="source", name="build")
    target_entity = _extract_function_entity(target, role="target", name="build")

    rules, _, _ = compile_rules(source_entities, Mock())
    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches={
            source_entity.canonical_id: MatchResult(
                source_id=source_entity.canonical_id,
                status=MatchStatus.MATCHED,
                target_id=target_entity.canonical_id,
                confidence=1.0,
                reasons=[],
                candidates=[],
            )
        },
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["OK", "OK"]


def test_api001_return_annotation_rejects_target_supertype() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_entity_signature

class ChildResult:
    pass

def build() -> ChildResult:
    __archtest__: Annotated[
        None,
        required_entity_signature(return_annotation="error"),
    ]
    raise NotImplementedError
"""
    target = """
class ChildResult:
    pass

class BaseResult:
    pass

def build() -> BaseResult:
    return BaseResult()
"""
    source_entities = _extract_entities(source, role="source")
    target_entities = _extract_entities(target, role="target")
    source_entity = _extract_function_entity(source, role="source", name="build")
    target_entity = _extract_function_entity(target, role="target", name="build")

    rules, _, _ = compile_rules(source_entities, Mock())
    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches={
            source_entity.canonical_id: MatchResult(
                source_id=source_entity.canonical_id,
                status=MatchStatus.MATCHED,
                target_id=target_entity.canonical_id,
                confidence=1.0,
                reasons=[],
                candidates=[],
            )
        },
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["OK", "FAILED"]
    assert "return annotation mismatch" in results[1].message


def test_api001_parameter_annotation_accepts_target_supertype() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_entity_signature

class Animal:
    pass

class Dog(Animal):
    pass

def handle(pet: Dog) -> None:
    __archtest__: Annotated[None, required_entity_signature()]
    return None
"""
    target = """
class Animal:
    pass

class Dog(Animal):
    pass

def handle(pet: Animal) -> None:
    return None
"""
    source_entities = _extract_entities(source, role="source")
    target_entities = _extract_entities(target, role="target")
    source_entity = _extract_function_entity(source, role="source", name="handle")
    target_entity = _extract_function_entity(target, role="target", name="handle")

    rules, _, _ = compile_rules(source_entities, Mock())
    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches={
            source_entity.canonical_id: MatchResult(
                source_id=source_entity.canonical_id,
                status=MatchStatus.MATCHED,
                target_id=target_entity.canonical_id,
                confidence=1.0,
                reasons=[],
                candidates=[],
            )
        },
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["OK", "OK"]


def test_api001_parameter_annotation_rejects_target_subtype() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import required_entity_signature

class Animal:
    pass

class Dog(Animal):
    pass

def handle(pet: Animal) -> None:
    __archtest__: Annotated[None, required_entity_signature()]
    return None
"""
    target = """
class Animal:
    pass

class Dog(Animal):
    pass

def handle(pet: Dog) -> None:
    return None
"""
    source_entities = _extract_entities(source, role="source")
    target_entities = _extract_entities(target, role="target")
    source_entity = _extract_function_entity(source, role="source", name="handle")
    target_entity = _extract_function_entity(target, role="target", name="handle")

    rules, _, _ = compile_rules(source_entities, Mock())
    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches={
            source_entity.canonical_id: MatchResult(
                source_id=source_entity.canonical_id,
                status=MatchStatus.MATCHED,
                target_id=target_entity.canonical_id,
                confidence=1.0,
                reasons=[],
                candidates=[],
            )
        },
        config=Mock(),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED", "OK"]
    assert "parameter annotation mismatch" in results[0].message
