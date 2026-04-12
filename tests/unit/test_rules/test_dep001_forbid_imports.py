from __future__ import annotations

from pythonarchtesting.matching import MatchResult, MatchStatus
from tests.unit.test_rules._dep001_helpers import (
    build_source_index_from_rule_source,
    build_target_index_from_files,
    evaluate_dep001_rule,
)


def test_dep001_direct_mode_package_scope_detects_forbidden_imports_with_relative_resolution() -> (
    None
):
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
    target_index = build_target_index_from_files(
        {
            "assignment/core.py": """
from typing import TYPE_CHECKING

def run() -> int:
    import requests
    import requests.sessions
    if TYPE_CHECKING:
        import socket
    return 1
""",
            "assignment/sub/mod.py": """
def use_relative() -> int:
    from .. import utils
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
    assert (
        "DEP001 forbidden imports found in package 'assignment'" in results[0].message
    )
    assert results[0].details["scope"] == "package"
    assert results[0].details["scope_value"] == "assignment"
    imported_modules = [
        item["imported_module"] for item in results[0].details["occurrences"]
    ]
    assert "requests" in imported_modules
    assert "assignment.utils" in imported_modules
    assert "requests.sessions" not in imported_modules
    assert "socket" not in imported_modules
