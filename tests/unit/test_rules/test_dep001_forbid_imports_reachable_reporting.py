from __future__ import annotations

from pythonarchtesting.matching import MatchResult, MatchStatus
from tests.unit.test_rules._dep001_helpers import (
    build_source_index_from_rule_source,
    build_target_index_from_files,
    evaluate_dep001_rule,
    get_entity,
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
    target_index = build_target_index_from_files(
        {
            "assignment/x.py": """
import requests
""",
            "assignment/a.py": """
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
    target_files = {"assignment/entry.py": ""}
    target_files["assignment/entry.py"] = (
        "\n".join(f"import assignment.mid{index:02d}" for index in range(26)) + "\n"
    )
    for index in range(26):
        target_files[f"assignment/mid{index:02d}.py"] = "import requests\n"

    target_index = build_target_index_from_files(target_files)
    source_entity, source_index = build_source_index_from_rule_source(source)
    entry_module = get_entity(target_index.all_sorted, kind="module", name="entry")

    results, errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
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


def test_dep001_reachable_mode_uses_stable_evidence_ids_across_runs() -> None:
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
import requests
""",
        }
    )
    source_entity, source_index = build_source_index_from_rule_source(source)
    target_a_entity = get_entity(target_index.all_sorted, kind="module", name="a")
    match = MatchResult(
        source_id=source_entity.canonical_id,
        status=MatchStatus.MATCHED,
        target_id=target_a_entity.canonical_id,
        confidence=1.0,
        reasons=[],
        candidates=[],
    )

    first_results, first_errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
        match=match,
    )
    second_results, second_errors = evaluate_dep001_rule(
        source_entity=source_entity,
        source_index=source_index,
        target_index=target_index,
        match=match,
    )

    assert first_errors == []
    assert second_errors == []
    assert [item.evidence_id for item in first_results[0].evidence] == [
        item.evidence_id for item in second_results[0].evidence
    ]
