from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from src.core.evaluation import evaluate_rules_for_target
from src.entities import Entity, build_entity_index
from src.entities_extraction import extract_entities_from_source
from src.matching import MatchResult, MatchStatus
from src.rules.compilation import compile_rules


def _extract_entity(
    source_text: str,
    *,
    role: str,
    file_path: str,
    kind: str,
    name: str,
) -> Entity:
    entities = extract_entities_from_source(
        source_text=source_text,
        file_path=Path(file_path),
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


def test_dep001_compile_emits_forbid_imports_rule():
    source = """
from typing import Annotated
from src.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", "socket", scope="package", package="assignment"),
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
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["DEP001/forbid_imports/v1"]
    assert rules[0].rule_type == "import_policy"
    assert rules[0].params["forbidden"] == ["requests", "socket"]
    assert rules[0].params["scope"] == "package"
    assert rules[0].params["package"] == "assignment"
    assert rules[0].params["fail_on_unmatched"] is False


def test_dep001_compile_emits_forbid_imports_rule_from_annotation():
    source = """
from typing import Annotated
from src.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", "socket", scope="package", package="assignment"),
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
    rules, evidence, compiler_results = compile_rules([source_entity], Mock())

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["DEP001/forbid_imports/v1"]
    assert rules[0].rule_type == "import_policy"
    assert rules[0].params["forbidden"] == ["requests", "socket"]
    assert rules[0].params["scope"] == "package"
    assert rules[0].params["package"] == "assignment"
    assert rules[0].params["fail_on_unmatched"] is False


def test_dep001_package_scope_detects_forbidden_imports_with_relative_resolution():
    source = """
from typing import Annotated
from src.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports(
            "requests",
            "assignment.utils",
            "socket",
            scope="package",
            package="assignment",
            allow=["requests.sessions"],
            ignore_type_checking=True,
        ),
    ]
    return None
"""
    target_core = """
from typing import TYPE_CHECKING

def run() -> int:
    import requests
    import requests.sessions
    if TYPE_CHECKING:
        import socket
    return 1
"""
    target_sub = """
def use_relative() -> int:
    from .. import utils
    return 1
"""
    source_entity = _extract_entity(
        source,
        role="source",
        file_path="assignment/rules.py",
        kind="function",
        name="_architecture_rules_marker",
    )
    target_run = _extract_entity(
        target_core,
        role="target",
        file_path="assignment/core.py",
        kind="function",
        name="run",
    )
    target_relative = _extract_entity(
        target_sub,
        role="target",
        file_path="assignment/sub/mod.py",
        kind="function",
        name="use_relative",
    )

    rules, _, _ = compile_rules([source_entity], Mock())
    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([target_run, target_relative])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.UNMATCHED,
            target_id=None,
            confidence=0.0,
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
    assert (
        "DEP001 forbidden imports found in package 'assignment'" in results[0].message
    )
    occurrences = results[0].details["occurrences"]
    imported_modules = [item["imported_module"] for item in occurrences]
    assert "requests" in imported_modules
    assert "assignment.utils" in imported_modules
    assert "requests.sessions" not in imported_modules
    assert "socket" not in imported_modules


def test_dep001_entity_scope_checks_only_matched_entity_module():
    source = """
from typing import Annotated
from src.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[None, forbid_imports("requests", scope="entity")]
    return None
"""
    target_safe = """
def safe() -> int:
    return 1
"""
    target_unsafe = """
def unsafe() -> int:
    import requests
    return 1
"""
    source_entity = _extract_entity(
        source,
        role="source",
        file_path="assignment/rules.py",
        kind="function",
        name="_architecture_rules_marker",
    )
    target_safe_entity = _extract_entity(
        target_safe,
        role="target",
        file_path="assignment/safe.py",
        kind="function",
        name="safe",
    )
    target_unsafe_entity = _extract_entity(
        target_unsafe,
        role="target",
        file_path="assignment/unsafe.py",
        kind="function",
        name="unsafe",
    )

    rules, _, _ = compile_rules([source_entity], Mock())
    source_index = build_entity_index([source_entity])
    target_index = build_entity_index([target_safe_entity, target_unsafe_entity])
    matches = {
        source_entity.canonical_id: MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_safe_entity.canonical_id,
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
