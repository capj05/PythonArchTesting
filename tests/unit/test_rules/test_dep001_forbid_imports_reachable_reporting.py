from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchResult, MatchStatus
from pythonarchtesting.rules.compilation import compile_rules


def _extract_entities(
    source_text: str,
    *,
    role: str,
    file_path: str,
) -> list[Entity]:
    return extract_entities_from_source(
        source_text=source_text,
        file_path=Path(file_path),
        root_path=Path("."),
        target_module_name=None,
        role=role,  # type: ignore[arg-type]
        include_nested_functions=False,
        root_label=role,
    )


def _extract_entity(
    source_text: str,
    *,
    role: str,
    file_path: str,
    kind: str,
    name: str,
) -> Entity:
    for entity in _extract_entities(source_text, role=role, file_path=file_path):
        if entity.kind == kind and entity.name == name:
            return entity
    raise AssertionError(f"Entity '{name}' ({kind}) not found for role={role}")


def _evaluate_dep001_rule(
    *,
    source_entity: Entity,
    target_entities: list[Entity],
    match: MatchResult,
):
    rules, _, _ = compile_rules([source_entity], Mock())
    source_index = build_entity_index([source_entity])
    target_index = build_entity_index(target_entities)
    matches = {source_entity.canonical_id: match}
    return evaluate_rules_for_target(
        rules=rules,
        source_index=source_index,
        target_index=target_index,
        matches=matches,
        config=Mock(),
    )


def test_dep001_reachable_mode_failed_result_includes_path_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", scope="module", mode="reachable"),
    ]
    return None
"""
    target_a = """
from assignment import b
"""
    target_b = """
from assignment import c
"""
    target_c = """
import requests
"""
    source_entity = _extract_entity(
        source,
        role="source",
        file_path="assignment/rules.py",
        kind="function",
        name="_architecture_rules_marker",
    )
    target_a_entities = _extract_entities(
        target_a,
        role="target",
        file_path="assignment/a.py",
    )
    target_b_entities = _extract_entities(
        target_b,
        role="target",
        file_path="assignment/b.py",
    )
    target_c_entities = _extract_entities(
        target_c,
        role="target",
        file_path="assignment/c.py",
    )
    target_a_entity = next(
        entity for entity in target_a_entities if entity.kind == "module"
    )

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=[*target_a_entities, *target_b_entities, *target_c_entities],
        match=MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_a_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    result = results[0]
    assert result.message == (
        "DEP001 reachable forbidden import paths found in module "
        "'assignment.a': ['requests'] (1 path)"
    )
    assert len(result.evidence) == 1
    assert result.evidence[0].type == "import_path"
    assert result.evidence[0].source == "ast"
    assert result.evidence[0].role == "target"
    assert result.evidence[0].location == {
        "filepath": "assignment/a.py",
        "lineno": 2,
        "module": "assignment.a",
    }
    assert result.evidence[0].payload == {
        "forbidden_prefix": "requests",
        "forbidden_target": "requests",
        "intermediate_modules": ["assignment.b", "assignment.c"],
        "mode": "reachable",
        "path_length": 3,
        "scope": "module",
        "scope_value": "assignment.a",
        "start_module": "assignment.a",
        "steps": [
            {
                "filepath": "assignment/a.py",
                "from_module": "assignment.a",
                "in_type_checking": False,
                "is_top_level": True,
                "lineno": 2,
                "to_module": "assignment.b",
            },
            {
                "filepath": "assignment/b.py",
                "from_module": "assignment.b",
                "in_type_checking": False,
                "is_top_level": True,
                "lineno": 2,
                "to_module": "assignment.c",
            },
            {
                "filepath": "assignment/c.py",
                "from_module": "assignment.c",
                "in_type_checking": False,
                "is_top_level": True,
                "lineno": 2,
                "to_module": "requests",
            },
        ],
    }
    assert result.details["occurrences"] == [
        {
            "filepath": "assignment/c.py",
            "lineno": 2,
            "imported_module": "requests",
            "forbidden_prefix": "requests",
        }
    ]
    assert result.details["path_count"] == 1
    assert result.details["path_count_total"] == 1
    assert result.details["path_count_reported"] == 1
    assert result.details["paths_truncated"] is False
    assert result.details["start_modules"] == ["assignment.a"]
    assert result.details["forbidden_targets"] == ["requests"]
    assert result.details["violation_paths"] == [
        {
            "start_module": "assignment.a",
            "intermediate_modules": ["assignment.b", "assignment.c"],
            "forbidden_target": "requests",
            "forbidden_prefix": "requests",
            "path_length": 3,
        }
    ]


def test_dep001_reachable_mode_orders_evidence_and_summaries_deterministically() -> (
    None
):
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", package="assignment", scope="package", mode="reachable"),
    ]
    return None
"""
    target_a = """
import requests
"""
    target_x = """
import requests
"""
    source_entity = _extract_entity(
        source,
        role="source",
        file_path="assignment/rules.py",
        kind="function",
        name="_architecture_rules_marker",
    )
    target_a_entities = _extract_entities(
        target_a,
        role="target",
        file_path="assignment/a.py",
    )
    target_x_entities = _extract_entities(
        target_x,
        role="target",
        file_path="assignment/x.py",
    )

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=[*target_x_entities, *target_a_entities],
        match=MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.UNMATCHED,
            target_id=None,
            confidence=0.0,
            reasons=[],
            candidates=[],
        ),
    )

    assert errors == []
    result = results[0]
    assert [item.payload["start_module"] for item in result.evidence] == [
        "assignment.a",
        "assignment.x",
    ]
    assert [item["start_module"] for item in result.details["violation_paths"]] == [
        "assignment.a",
        "assignment.x",
    ]
    assert result.details["start_modules"] == ["assignment.a", "assignment.x"]


def test_dep001_reachable_mode_reports_truncation_metadata() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", scope="module", mode="reachable"),
    ]
    return None
"""
    source_entity = _extract_entity(
        source,
        role="source",
        file_path="assignment/rules.py",
        kind="function",
        name="_architecture_rules_marker",
    )

    target_entities: list[Entity] = []
    import_lines = [f"import assignment.mid{index:02d}" for index in range(26)]
    entry_entities = _extract_entities(
        "\n".join(import_lines) + "\n",
        role="target",
        file_path="assignment/entry.py",
    )
    target_entities.extend(entry_entities)
    for index in range(26):
        middle_name = f"mid{index:02d}"
        target_entities.extend(
            _extract_entities(
                "import requests\n",
                role="target",
                file_path=f"assignment/{middle_name}.py",
            )
        )
    entry_module = next(entity for entity in entry_entities if entity.kind == "module")

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=target_entities,
        match=MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=entry_module.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    )

    assert errors == []
    result = results[0]
    assert result.status == "FAILED"
    assert len(result.evidence) == 25
    assert result.details["path_count"] == 26
    assert result.details["path_count_total"] == 26
    assert result.details["path_count_reported"] == 25
    assert result.details["paths_truncated"] is True
    assert len(result.details["violation_paths"]) == 25
    assert "26 paths" in result.message
