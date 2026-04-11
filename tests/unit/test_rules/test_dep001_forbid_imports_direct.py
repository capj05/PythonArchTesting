from __future__ import annotations

from pythonarchtesting.matching import MatchResult, MatchStatus
from tests.unit.test_rules._dep001_helpers import (
    build_source_index_from_rule_source,
    build_target_index_from_files,
    evaluate_dep001_rule,
    get_entity,
)


def test_dep001_direct_mode_module_scope_checks_only_matched_module() -> None:
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
            "assignment/safe.py": """
def safe() -> int:
    return 1
""",
            "assignment/unsafe.py": """
def unsafe() -> int:
    import requests
    return 1
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
    target_index = build_target_index_from_files(
        {
            "assignment/a.py": """
from assignment import b

def use_b() -> int:
    return 1
""",
            "assignment/b.py": """
import requests

def run() -> int:
    return 1
""",
        }
    )
    direct_source_entity, direct_source_index = build_source_index_from_rule_source(
        source_direct,
        file_path="assignment/direct_rules.py",
    )
    default_source_entity, default_source_index = build_source_index_from_rule_source(
        source_default,
        file_path="assignment/default_rules.py",
    )
    target_a_entity = get_entity(
        target_index.all_sorted,
        kind="function",
        name="use_b",
    )

    direct_results, direct_errors = evaluate_dep001_rule(
        source_entity=direct_source_entity,
        source_index=direct_source_index,
        target_index=target_index,
        match=MatchResult(
            source_id=direct_source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_a_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    )
    reachable_results, reachable_errors = evaluate_dep001_rule(
        source_entity=default_source_entity,
        source_index=default_source_index,
        target_index=target_index,
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
    assert [result.status for result in reachable_results] == ["FAILED"]
    assert reachable_results[0].details["mode"] == "reachable"
    assert reachable_results[0].details["scope"] == "module"
    assert reachable_results[0].details["scope_value"] == "assignment.a"
    assert [
        item["imported_module"] for item in reachable_results[0].details["occurrences"]
    ] == ["requests"]


def test_dep001_direct_mode_reports_nested_local_imports() -> None:
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
def run() -> int:
    def inner() -> None:
        import requests

    inner()
    return 1
""",
        }
    )
    source_entity, source_index = build_source_index_from_rule_source(source)
    target_run_entity = get_entity(
        target_index.all_sorted,
        kind="function",
        name="run",
    )

    results, errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
        match=MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_run_entity.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    )

    assert errors == []
    assert [result.status for result in results] == ["FAILED"]
    assert results[0].details["occurrences"] == [
        {
            "filepath": "assignment/core.py",
            "lineno": 4,
            "imported_module": "requests",
            "forbidden_prefix": "requests",
        }
    ]


def test_dep001_direct_mode_deduplicates_occurrences_from_overlapping_entities() -> (
    None
):
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
    assert results[0].details["occurrences"] == [
        {
            "filepath": "assignment/core.py",
            "lineno": 6,
            "imported_module": "requests",
            "forbidden_prefix": "requests",
        }
    ]
