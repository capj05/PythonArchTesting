from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

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


def test_dep001_compile_defaults_to_reachable_mode_and_v2_rule_id() -> None:
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


def test_dep001_compile_honors_explicit_modes() -> None:
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
    target_entities = [
        *_extract_entities(target_core, role="target", file_path="assignment/core.py"),
        *_extract_entities(
            target_sub,
            role="target",
            file_path="assignment/sub/mod.py",
        ),
    ]

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=target_entities,
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


def test_dep001_default_reachable_mode_detects_top_level_forbidden_import() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

def _architecture_rules_marker() -> None:
    __archtest__: Annotated[None, forbid_imports("requests", scope="package")]
    return None
"""
    target = """
import requests

def run() -> int:
    return 1
"""
    source_entity = _extract_entity(
        source,
        role="source",
        file_path="assignment/rules.py",
        kind="function",
        name="_architecture_rules_marker",
    )
    target_entities = _extract_entities(
        target,
        role="target",
        file_path="assignment/core.py",
    )

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=target_entities,
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


def test_dep001_reachable_mode_fails_for_internal_chain_to_forbidden_external() -> None:
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
from assignment import b

def use_b() -> int:
    return 1
"""
    target_b = """
import requests

def run() -> int:
    return 1
"""
    source_entity = _extract_entity(
        source,
        role="source",
        file_path="assignment/rules.py",
        kind="function",
        name="_architecture_rules_marker",
    )
    target_entities = [
        *_extract_entities(target_a, role="target", file_path="assignment/a.py"),
        *_extract_entities(target_b, role="target", file_path="assignment/b.py"),
    ]

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=target_entities,
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
    target_safe_entities = _extract_entities(
        target_safe,
        role="target",
        file_path="assignment/safe.py",
    )
    target_unsafe_entities = _extract_entities(
        target_unsafe,
        role="target",
        file_path="assignment/unsafe.py",
    )
    target_safe_entity = next(
        entity
        for entity in target_safe_entities
        if entity.kind == "function" and entity.name == "safe"
    )

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=[*target_safe_entities, *target_unsafe_entities],
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
    target_entities = _extract_entities(
        target_module,
        role="target",
        file_path="assignment/core.py",
    )
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
from assignment import b

def use_b() -> int:
    return 1
"""
    target_b = """
import requests

def run() -> int:
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
    target_a_entity = next(
        entity
        for entity in target_a_entities
        if entity.kind == "function" and entity.name == "use_b"
    )
    target_entities = [*target_a_entities, *target_b_entities]

    direct_results, direct_errors = _evaluate_dep001_rule(
        source_entity=direct_source_entity,
        target_entities=target_entities,
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
        target_entities=target_entities,
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
    target_a = """
from assignment import b
"""
    target_b = """
def lazy() -> int:
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
    target_a_entity = next(
        entity for entity in target_a_entities if entity.kind == "module"
    )

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=[*target_a_entities, *target_b_entities],
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
    target_a = """
from assignment import b
"""
    target_b = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
    target_a_entity = next(
        entity for entity in target_a_entities if entity.kind == "module"
    )

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=[*target_a_entities, *target_b_entities],
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
    target_a = """
from assignment import b
"""
    target_b = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
    target_a_entity = next(
        entity for entity in target_a_entities if entity.kind == "module"
    )

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=[*target_a_entities, *target_b_entities],
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
    target_a = """
import assignment.adapters.http
"""
    target_http = """
import requests
"""
    source_entity = _extract_entity(
        source,
        role="source",
        file_path="assignment/rules.py",
        kind="function",
        name="_architecture_rules_marker",
    )
    target_entities = [
        *_extract_entities(target_a, role="target", file_path="assignment/a.py"),
        *_extract_entities(
            target_http,
            role="target",
            file_path="assignment/adapters/http.py",
        ),
    ]

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=target_entities,
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
    target_a = """
import assignment.generated.client
"""
    target_generated = """
import requests
"""
    source_entity = _extract_entity(
        source,
        role="source",
        file_path="assignment/rules.py",
        kind="function",
        name="_architecture_rules_marker",
    )
    target_entities = [
        *_extract_entities(target_a, role="target", file_path="assignment/a.py"),
        *_extract_entities(
            target_generated,
            role="target",
            file_path="assignment/generated/client.py",
        ),
    ]

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=target_entities,
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
    target_safe = """
def safe() -> int:
    return 1
"""
    target_unsafe = """
import requests
"""
    source_entity = _extract_entity(
        source,
        role="source",
        file_path="assignment/rules.py",
        kind="function",
        name="_architecture_rules_marker",
    )
    safe_entities = _extract_entities(
        target_safe,
        role="target",
        file_path="assignment/safe.py",
    )
    unsafe_entities = _extract_entities(
        target_unsafe,
        role="target",
        file_path="assignment/unsafe.py",
    )
    safe_function = next(
        entity
        for entity in safe_entities
        if entity.kind == "function" and entity.name == "safe"
    )

    results, errors = _evaluate_dep001_rule(
        source_entity=source_entity,
        target_entities=[*safe_entities, *unsafe_entities],
        match=MatchResult(
            source_id=source_entity.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=safe_function.canonical_id,
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
    target_entities = _extract_entities(
        target_module,
        role="target",
        file_path="assignment/core.py",
    )
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
    assert results[0].details["occurrences"] == [
        {
            "filepath": "assignment/core.py",
            "lineno": 6,
            "imported_module": "requests",
            "forbidden_prefix": "requests",
        }
    ]


def test_dep001_helper_rejects_invalid_mode() -> None:
    from pythonarchtesting.rules import forbid_imports

    with pytest.raises(
        ValueError,
        match="forbid_imports\\(\\) mode must be 'reachable' or 'direct'\\.",
    ):
        forbid_imports("requests", mode="invalid")
