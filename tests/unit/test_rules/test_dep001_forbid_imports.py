from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchResult, MatchStatus
from pythonarchtesting.rules.compilation import compile_rules


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


def test_dep001_compile_defaults_to_reachable_mode_and_v2_rule_id():
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

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
    assert [rule.rule_id for rule in rules] == ["DEP001/forbid_imports/v2"]
    assert rules[0].rule_type == "import_policy"
    assert rules[0].params["forbidden"] == ["requests", "socket"]
    assert rules[0].params["mode"] == "reachable"
    assert rules[0].params["scope"] == "package"
    assert rules[0].params["package"] == "assignment"
    assert rules[0].params["fail_on_unmatched"] is False


def test_dep001_compile_honors_explicit_modes():
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", mode="reachable"),
    ]
    __archtest__: Annotated[
        None,
        forbid_imports("socket", mode="direct"),
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
    assert [rule.rule_id for rule in rules] == [
        "DEP001/forbid_imports/v2/d0",
        "DEP001/forbid_imports/v2/d1",
    ]
    assert [rule.params["mode"] for rule in rules] == ["reachable", "direct"]


def test_dep001_compile_normalizes_scope_values() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", scope="module"),
    ]
    __archtest__: Annotated[
        None,
        forbid_imports("socket", scope="entity"),
    ]
    __archtest__: Annotated[
        None,
        forbid_imports("subprocess", scope="nonsense"),
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
    assert [rule.params["scope"] for rule in rules] == ["module", "module", "package"]


def test_dep001_compile_invalid_raw_mode_emits_compiler_error_evidence() -> None:
    source = """
from typing import Annotated

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        ("forbid_imports", {"forbidden": ["requests"], "mode": "invalid"}),
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

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_import_policy_mode"]
    assert evidence[0].payload["issue"] == "invalid_mode"
    assert evidence[0].payload["severity"] == "error"


def test_dep001_direct_mode_package_scope_detects_forbidden_imports_with_relative_resolution():
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports(
            "requests",
            "assignment.utils",
            "socket",
            scope="package",
            package="assignment",
            mode="direct",
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

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=[target_run, target_relative],
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
    assert [result.status for result in results] == ["FAILED"]
    assert (
        "DEP001 forbidden imports found in package 'assignment'" in results[0].message
    )
    assert results[0].details["scope"] == "package"
    assert results[0].details["scope_value"] == "assignment"
    occurrences = results[0].details["occurrences"]
    imported_modules = [item["imported_module"] for item in occurrences]
    assert "requests" in imported_modules
    assert "assignment.utils" in imported_modules
    assert "requests.sessions" not in imported_modules
    assert "socket" not in imported_modules


def test_dep001_default_mode_returns_reachable_not_implemented_error():
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[None, forbid_imports("requests", scope="package")]
    return None
"""
    target = """
def run() -> int:
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
    target_entity = _extract_entity(
        target,
        role="target",
        file_path="assignment/core.py",
        kind="function",
        name="run",
    )

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=[target_entity],
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
    assert [result.status for result in results] == ["ERROR"]
    assert results[0].message == (
        "DEP001 reachable import policy mode is the default semantic contract, "
        "but reachability analysis is not implemented yet."
    )
    assert results[0].details["mode"] == "reachable"
    assert results[0].details["reason"] == "reachable_mode_not_implemented"
    assert results[0].details["scope"] == "package"
    assert results[0].details["scope_value"] == "assignment"


def test_dep001_reachable_mode_returns_not_implemented_error_for_indirect_case():
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
def use_b() -> int:
    from assignment import b
    return b.run()
"""
    target_b = """
def run() -> int:
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
    target_a_entity = _extract_entity(
        target_a,
        role="target",
        file_path="assignment/a.py",
        kind="function",
        name="use_b",
    )
    target_b_entity = _extract_entity(
        target_b,
        role="target",
        file_path="assignment/b.py",
        kind="function",
        name="run",
    )

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=[target_a_entity, target_b_entity],
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
    assert [result.status for result in results] == ["ERROR"]
    assert results[0].details["mode"] == "reachable"
    assert results[0].details["reason"] == "reachable_mode_not_implemented"
    assert results[0].details["scope"] == "package"
    assert results[0].details["scope_value"] == "assignment"


def test_dep001_direct_mode_module_scope_checks_only_matched_module():
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", scope="module", mode="direct"),
    ]
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

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=[target_safe_entity, target_unsafe_entity],
        match=MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_safe_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    )

    assert errors == []
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["mode"] == "direct"
    assert results[0].details["scope"] == "module"
    assert results[0].details["scope_value"] == "assignment.safe"


def test_dep001_direct_mode_module_scope_is_file_wide_not_entity_local() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", scope="module", mode="direct"),
    ]
    return None
"""
    target_module = """
def safe() -> int:
    return 1

def unsafe() -> int:
    import requests
    return 2
"""
    source_entity = _extract_entity(
        source,
        role="source",
        file_path="assignment/rules.py",
        kind="function",
        name="_architecture_rules_marker",
    )
    target_entities = extract_entities_from_source(
        source_text=target_module,
        file_path=Path("assignment/core.py"),
        root_path=Path("."),
        target_module_name=None,
        role="target",
        include_nested_functions=False,
        root_label="target",
    )
    target_entities = [
        entity for entity in target_entities if entity.kind == "function"
    ]
    target_safe_entity = next(
        entity
        for entity in target_entities
        if entity.kind == "function" and entity.name == "safe"
    )

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=target_entities,
        match=MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_safe_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert (
        "DEP001 forbidden imports found in module 'assignment.core'"
        in results[0].message
    )
    assert results[0].details["scope"] == "module"
    assert results[0].details["scope_value"] == "assignment.core"
    assert [item["imported_module"] for item in results[0].details["occurrences"]] == [
        "requests"
    ]


def test_dep001_direct_and_reachable_modes_diverge_for_indirect_imports() -> None:
    source_direct = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", scope="module", mode="direct"),
    ]
    return None
"""
    source_default = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", scope="module"),
    ]
    return None
"""
    target_a = """
def use_b() -> int:
    from assignment import b
    return b.run()
"""
    target_b = """
def run() -> int:
    import requests
    return 1
"""
    direct_source_entity = _extract_entity(
        source_direct,
        role="source",
        file_path="assignment/direct_rules.py",
        kind="function",
        name="_architecture_rules_marker",
    )
    default_source_entity = _extract_entity(
        source_default,
        role="source",
        file_path="assignment/default_rules.py",
        kind="function",
        name="_architecture_rules_marker",
    )
    target_a_entity = _extract_entity(
        target_a,
        role="target",
        file_path="assignment/a.py",
        kind="function",
        name="use_b",
    )
    target_b_entity = _extract_entity(
        target_b,
        role="target",
        file_path="assignment/b.py",
        kind="function",
        name="run",
    )
    direct_results, direct_errors = _evaluate_dep001_rule(
        source_entity=direct_source_entity,
        target_entities=[target_a_entity, target_b_entity],
        match=MatchResult(
            source_id=direct_source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_a_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    )
    reachable_results, reachable_errors = _evaluate_dep001_rule(
        source_entity=default_source_entity,
        target_entities=[target_a_entity, target_b_entity],
        match=MatchResult(
            source_id=default_source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_a_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    )

    assert direct_errors == []
    assert [result.status for result in direct_results] == ["OK"]
    assert direct_results[0].details["mode"] == "direct"
    assert direct_results[0].details["scope"] == "module"
    assert direct_results[0].details["scope_value"] == "assignment.a"

    assert reachable_errors == []
    assert [result.status for result in reachable_results] == ["ERROR"]
    assert reachable_results[0].details["mode"] == "reachable"
    assert reachable_results[0].details["scope"] == "module"
    assert reachable_results[0].details["scope_value"] == "assignment.a"


def test_dep001_helper_rejects_invalid_mode() -> None:
    from pythonarchtesting.rules import forbid_imports

    with pytest.raises(
        ValueError,
        match="forbid_imports\\(\\) mode must be 'reachable' or 'direct'\\.",
    ):
        forbid_imports("requests", mode="invalid")
