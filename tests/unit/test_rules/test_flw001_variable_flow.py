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


def _extract_function(source_text: str, *, role: str, name: str) -> Entity:
    for entity in _extract_entities(source_text, role=role):
        if entity.kind == "function" and entity.name == name:
            return entity
    raise AssertionError(f"Function '{name}' not found for role={role}")


def _match_for(source_entity: Entity, target_entity: Entity) -> dict[str, MatchResult]:
    return {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        )
    }


def _evaluate_single_rule(source: str, target: str) -> list:
    source_entities = _extract_entities(source, role="source")
    target_entities = _extract_entities(target, role="target")
    source_entity = _extract_function(source, role="source", name="process")
    target_entity = _extract_function(target, role="target", name="process")
    rules, evidence, _ = compile_rules(source_entities, Mock())
    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["FLW001/enforce_flow/v1"]
    results, errors = evaluate_rules_for_target(
        rules=rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches=_match_for(source_entity, target_entity),
        config=Mock(),
    )
    assert errors == []
    return results


def test_flw001_evaluation_passes_for_linear_flow() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import enforce_flow, flow

def process(value: str) -> str:
    current = value
    __archtest__: Annotated[None, flow("raw")]
    current = current.strip()
    __archtest__: Annotated[None, flow("validated")]
    __archtest__: Annotated[None, enforce_flow(["raw", "validated"])]
    return current
"""
    target = """
from typing import Annotated
from pythonarchtesting.rules import flow

def process(value: str) -> str:
    current = value
    __archtest__: Annotated[None, flow("raw")]
    current = current.strip()
    __archtest__: Annotated[None, flow("validated")]
    return current
"""
    results = _evaluate_single_rule(source, target)
    assert [result.status for result in results] == ["OK"]


def test_flw001_evaluation_passes_when_all_branches_satisfy_flow() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import enforce_flow, flow

def process(value: str) -> str:
    current = value
    __archtest__: Annotated[None, flow("raw")]
    current = current.strip()
    __archtest__: Annotated[None, flow("validated")]
    __archtest__: Annotated[None, enforce_flow(["raw", "validated"])]
    return current
"""
    target = """
from typing import Annotated
from pythonarchtesting.rules import flow

def process(value: str) -> str:
    current = value
    __archtest__: Annotated[None, flow("raw")]
    if value:
        current = current.strip()
        __archtest__: Annotated[None, flow("validated")]
    else:
        current = current.upper()
        __archtest__: Annotated[None, flow("validated")]
    return current
"""
    results = _evaluate_single_rule(source, target)
    assert [result.status for result in results] == ["OK"]


def test_flw001_evaluation_fails_when_one_branch_skips_stage() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import enforce_flow, flow

def process(value: str) -> str:
    current = value
    __archtest__: Annotated[None, flow("raw")]
    current = current.strip()
    __archtest__: Annotated[None, flow("validated")]
    __archtest__: Annotated[None, enforce_flow(["raw", "validated"])]
    return current
"""
    target = """
from typing import Annotated
from pythonarchtesting.rules import flow

def process(value: str) -> str:
    current = value
    __archtest__: Annotated[None, flow("raw")]
    if value:
        current = current.strip()
        __archtest__: Annotated[None, flow("validated")]
    return current
"""
    results = _evaluate_single_rule(source, target)
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "missing_stages"


def test_flw001_evaluation_fails_for_early_return_path() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import enforce_flow, flow

def process(value: str) -> str:
    current = value
    __archtest__: Annotated[None, flow("raw")]
    current = current.strip()
    __archtest__: Annotated[None, flow("validated")]
    __archtest__: Annotated[None, enforce_flow(["raw", "validated"])]
    return current
"""
    target = """
from typing import Annotated
from pythonarchtesting.rules import flow

def process(value: str) -> str:
    current = value
    __archtest__: Annotated[None, flow("raw")]
    if not value:
        return current
    current = current.strip()
    __archtest__: Annotated[None, flow("validated")]
    return current
"""
    results = _evaluate_single_rule(source, target)
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "missing_stages"


def test_flw001_evaluation_fails_for_out_of_order_stage() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import enforce_flow, flow

def process(value: str) -> str:
    current = value
    __archtest__: Annotated[None, flow("raw")]
    current = current.strip()
    __archtest__: Annotated[None, flow("validated")]
    __archtest__: Annotated[None, enforce_flow(["raw", "validated"])]
    return current
"""
    target = """
from typing import Annotated
from pythonarchtesting.rules import flow

def process(value: str) -> str:
    current = value.strip()
    __archtest__: Annotated[None, flow("validated")]
    current = value
    __archtest__: Annotated[None, flow("raw")]
    return current
"""
    results = _evaluate_single_rule(source, target)
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["failure_reason"] == "out_of_order_stage"
