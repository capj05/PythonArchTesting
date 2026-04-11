from __future__ import annotations

from pythonarchtesting.matching import MatchResult, MatchStatus
from tests.unit.test_rules._dep001_helpers import (
    build_source_index_from_rule_source,
    build_target_index_from_files,
    evaluate_dep001_rule,
    get_entity,
)


def test_dep001_reachable_mode_respects_ignore_type_checking_true() -> None:
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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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


def test_dep001_reachable_mode_fails_when_ignore_type_checking_false() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports(
            "requests",
            scope="module",
            mode="reachable",
            ignore_type_checking=False,
        ),
    ]
    return None
"""
    target_index = build_target_index_from_files(
        {
            "assignment/a.py": """
from assignment import b
""",
            "assignment/b.py": """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
    assert [item["imported_module"] for item in results[0].details["occurrences"]] == [
        "requests"
    ]


def test_dep001_reachable_mode_prunes_allowed_prefix() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports(
            "requests",
            package="assignment",
            scope="package",
            mode="reachable",
            allow=["assignment.adapters"],
        ),
    ]
    return None
"""
    target_index = build_target_index_from_files(
        {
            "assignment/a.py": """
import assignment.adapters.http
""",
            "assignment/adapters/http.py": """
import requests
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
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["occurrences"] == []


def test_dep001_reachable_mode_excludes_ignored_files_from_graph() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports(
            "requests",
            package="assignment",
            scope="package",
            mode="reachable",
            ignore_globs=["assignment/generated/*"],
        ),
    ]
    return None
"""
    target_index = build_target_index_from_files(
        {
            "assignment/a.py": """
import assignment.generated.client
""",
            "assignment/generated/client.py": """
import requests
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
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["occurrences"] == []


def test_dep001_direct_mode_excludes_ignored_files_from_package_scan() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[
        None,
        forbid_imports(
            "requests",
            package="assignment",
            scope="package",
            mode="direct",
            ignore_globs=["assignment/generated/*"],
        ),
    ]
    return None
"""
    target_index = build_target_index_from_files(
        {
            "assignment/core.py": """
import json
""",
            "assignment/generated/client.py": """
import requests
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
    assert [result.status for result in results] == ["OK"]
    assert results[0].details["occurrences"] == []
