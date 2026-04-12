from __future__ import annotations

from pythonarchtesting.matching import MatchResult, MatchStatus
from tests.unit.test_rules._dep001_helpers import (
    build_source_index_from_rule_source,
    build_target_index_from_files,
    evaluate_dep001_rule,
    get_entity,
)


def test_dep001_scope_module_uses_full_same_module_index() -> None:
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
    target_index = build_target_index_from_files(
        {
            "assignment/core.py": """
CONSTANT = 1

def safe() -> int:
    return CONSTANT

class Adapter:
    def call(self) -> int:
        import requests
        return 2
""",
        }
    )
    source_entity, source_index = build_source_index_from_rule_source(source)
    target_safe_entity = get_entity(
        target_index.all_sorted,
        kind="function",
        name="safe",
    )

    results, errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
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
    assert results[0].details["scope"] == "module"
    assert results[0].details["scope_value"] == "assignment.core"
    assert [item["imported_module"] for item in results[0].details["occurrences"]] == [
        "requests"
    ]


def test_dep001_scope_entity_alias_maps_to_module_behavior() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", scope="entity", mode="direct"),
    ]
    return None
"""
    target_index = build_target_index_from_files(
        {
            "assignment/core.py": """
def safe() -> int:
    return 1

def unsafe() -> int:
    import requests
    return 2
""",
        }
    )
    source_entity, source_index = build_source_index_from_rule_source(source)
    target_safe_entity = get_entity(
        target_index.all_sorted,
        kind="function",
        name="safe",
    )

    results, errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
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
    assert results[0].details["scope"] == "module"
    assert results[0].details["scope_value"] == "assignment.core"


def test_dep001_scope_package_uses_full_package_index() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("requests", package="assignment", scope="package", mode="direct"),
    ]
    return None
"""
    target_index = build_target_index_from_files(
        {
            "assignment/safe.py": """
def safe() -> int:
    return 1
""",
            "assignment/sub/unsafe.py": """
def unsafe() -> int:
    import requests
    return 2
""",
        }
    )
    source_entity, source_index = build_source_index_from_rule_source(source)
    target_safe_entity = get_entity(
        target_index.all_sorted,
        kind="function",
        name="safe",
    )

    results, errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
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
    assert results[0].details["scope"] == "package"
    assert results[0].details["scope_value"] == "assignment"
    assert [item["imported_module"] for item in results[0].details["occurrences"]] == [
        "requests"
    ]
