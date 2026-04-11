from __future__ import annotations

from pythonarchtesting.matching import MatchResult, MatchStatus
from tests.unit.test_rules._dep001_helpers import (
    build_source_index_from_rule_source,
    build_target_index_from_files,
    evaluate_dep001_rule,
    get_entity,
)


def test_dep001_default_reachable_mode_detects_top_level_forbidden_import() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[None, forbid_imports("requests", scope="package")]
    return None
"""
    target_index = build_target_index_from_files(
        {
            "assignment/core.py": """
import requests

def run() -> int:
    return 1
""",
        }
    )
    source_entity, source_index = build_source_index_from_rule_source(source)

    results, errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
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
    assert results[0].details["mode"] == "reachable"
    assert results[0].details["scope"] == "package"
    assert results[0].details["scope_value"] == "assignment"
    assert [item["imported_module"] for item in results[0].details["occurrences"]] == [
        "requests"
    ]


def test_dep001_reachable_mode_fails_for_multi_hop_internal_chain() -> None:
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
    target_index = build_target_index_from_files(
        {
            "assignment/a.py": """
from assignment import b
""",
            "assignment/b.py": """
from assignment import c
""",
            "assignment/c.py": """
import requests
""",
        }
    )
    source_entity, source_index = build_source_index_from_rule_source(source)
    target_a_entity = get_entity(target_index.all_sorted, kind="module", name="a")

    results, errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
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
    assert results[0].details["violation_paths"] == [
        {
            "start_module": "assignment.a",
            "intermediate_modules": ["assignment.b", "assignment.c"],
            "forbidden_target": "requests",
            "forbidden_prefix": "requests",
            "path_length": 3,
        }
    ]


def test_dep001_reachable_mode_passes_when_no_forbidden_target_is_reachable() -> None:
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
    target_index = build_target_index_from_files(
        {
            "assignment/a.py": """
from assignment import b
""",
            "assignment/b.py": """
import json
""",
        }
    )
    source_entity, source_index = build_source_index_from_rule_source(source)
    target_a_entity = get_entity(target_index.all_sorted, kind="module", name="a")

    results, errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
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
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["occurrences"] == []
    assert results[0].details["violation_paths"] == []


def test_dep001_reachable_mode_stops_at_external_modules() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports("urllib3", scope="module", mode="reachable"),
    ]
    return None
"""
    target_index = build_target_index_from_files(
        {
            "assignment/a.py": """
import requests
""",
        }
    )
    source_entity, source_index = build_source_index_from_rule_source(source)
    target_a_entity = get_entity(target_index.all_sorted, kind="module", name="a")

    results, errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
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
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["occurrences"] == []


def test_dep001_reachable_mode_ignores_local_only_forbidden_import_by_default() -> None:
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
    target_index = build_target_index_from_files(
        {
            "assignment/a.py": """
from assignment import b
""",
            "assignment/b.py": """
def lazy() -> int:
    import requests
    return 1
""",
        }
    )
    source_entity, source_index = build_source_index_from_rule_source(source)
    target_a_entity = get_entity(target_index.all_sorted, kind="module", name="a")

    results, errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
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
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["occurrences"] == []


def test_dep001_reachable_mode_fails_for_relative_import_chain() -> None:
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
    target_index = build_target_index_from_files(
        {
            "assignment/a.py": """
from .sub import mod
""",
            "assignment/sub/mod.py": """
from .. import utils
""",
            "assignment/utils.py": """
import requests
""",
        }
    )
    source_entity, source_index = build_source_index_from_rule_source(source)
    target_a_entity = get_entity(target_index.all_sorted, kind="module", name="a")

    results, errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
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
    assert results[0].details["forbidden_targets"] == ["requests"]
    assert results[0].details["start_modules"] == ["assignment.a"]


def test_dep001_reachable_mode_handles_relative_imports_from_package_init() -> None:
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
    target_index = build_target_index_from_files(
        {
            "assignment/a.py": """
import assignment.sub
""",
            "assignment/sub/__init__.py": """
from . import mod
""",
            "assignment/sub/mod.py": """
import requests
""",
        }
    )
    source_entity, source_index = build_source_index_from_rule_source(source)
    target_a_entity = get_entity(target_index.all_sorted, kind="module", name="a")

    results, errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
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
    assert results[0].details["violation_paths"] == [
        {
            "start_module": "assignment.a",
            "intermediate_modules": ["assignment.sub", "assignment.sub.mod"],
            "forbidden_target": "requests",
            "forbidden_prefix": "requests",
            "path_length": 3,
        }
    ]


def test_dep001_reachable_package_scope_uses_all_package_modules_as_roots() -> None:
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
    target_index = build_target_index_from_files(
        {
            "assignment/safe.py": """
def safe() -> int:
    return 1
""",
            "assignment/unsafe.py": """
import requests
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
    assert [item["imported_module"] for item in results[0].details["occurrences"]] == [
        "requests"
    ]
