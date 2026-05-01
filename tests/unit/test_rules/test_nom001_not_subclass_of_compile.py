from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.core.evaluation import evaluate_rules_for_target
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.matching import MatchResult, MatchStatus
from pythonarchtesting.rules.compilation import compile_rules


def _extract_entities(source: str, *, path: str) -> list[Entity]:
    return extract_entities_from_source(
        textwrap.dedent(source).strip() + "\n",
        Path(path),
        Path("."),
        None,
        role="source",
        include_nested_functions=False,
        root_label="source",
    )


def test_nom001_not_subclass_of_compile_emits_nominal_type_rule() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import not_subclass_of

class BaseRepository:
    pass


class CsvRepository:
    __archtest__: Annotated[None, not_subclass_of("source_module.BaseRepository")]
"""

    source_entities = _extract_entities(source, path="source_module.py")
    source_entity = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "CsvRepository"
    )

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert evidence == []
    assert compiler_results == []
    compiled_rules = [
        rule
        for rule in rules
        if rule.selector.source_entity_id == source_entity.canonical_id
    ]
    assert [rule.rule_id for rule in compiled_rules] == ["NOM001/not_subclass_of/v1"]
    assert compiled_rules[0].rule_type == "nominal_type_relationship"
    assert compiled_rules[0].params["base"] == "source_module.BaseRepository"
    assert (
        ":BaseRepository:class:" in compiled_rules[0].params["expected_source_base_id"]
    )
    assert compiled_rules[0].params["relationship_mode"] == "subclass"
    assert compiled_rules[0].params["allow_self"] is False
    assert compiled_rules[0].params["negated"] is True
    assert compiled_rules[0].params["fail_on_unmatched"] is True
    assert compiled_rules[0].params["transitive"] is True


def test_nom001_not_subclass_of_compile_non_class_emits_invalid_target_evidence() -> (
    None
):
    source = """
from typing import Annotated
from pythonarchtesting.rules import not_subclass_of

def build() -> None:
    __archtest__: Annotated[None, not_subclass_of("source_module.BaseRepository")]
"""

    source_entities = _extract_entities(source, path="source_module.py")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert len(rules) == 1
    assert rules[0].rule_type == "compiler_invalid_param"
    assert rules[0].params["decorator"] == "not_subclass_of"
    assert rules[0].params["param"] == "target_kind"
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


def test_nom001_not_subclass_of_compile_empty_base_emits_compiler_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import not_subclass_of

class CsvRepository:
    __archtest__: Annotated[None, not_subclass_of("")]
"""

    source_entities = _extract_entities(source, path="source_module.py")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert len(rules) == 1
    assert rules[0].rule_type == "compiler_invalid_param"
    assert rules[0].params["decorator"] == "not_subclass_of"
    assert rules[0].params["param"] == "base"
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_base_reference"]
    assert evidence[0].payload["reason"] == "missing_base"


def test_nom001_not_subclass_of_compile_unresolved_base_emits_compiler_evidence() -> (
    None
):
    source = """
from typing import Annotated
from pythonarchtesting.rules import not_subclass_of

class CsvRepository:
    __archtest__: Annotated[None, not_subclass_of("source_module.MissingBase")]
"""

    source_entities = _extract_entities(source, path="source_module.py")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert len(rules) == 1
    assert rules[0].rule_type == "compiler_invalid_param"
    assert rules[0].params["decorator"] == "not_subclass_of"
    assert rules[0].params["param"] == "base"
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_base_reference"]


def test_nom001_not_subclass_of_compile_ambiguous_simple_name_emits_compiler_evidence() -> (
    None
):
    source_entities = [
        *_extract_entities(
            """
class BaseRepository:
    pass
""",
            path="pkg_a/base.py",
        ),
        *_extract_entities(
            """
class BaseRepository:
    pass
""",
            path="pkg_b/base.py",
        ),
        *_extract_entities(
            """
from typing import Annotated
from pythonarchtesting.rules import not_subclass_of

class CsvRepository:
    __archtest__: Annotated[None, not_subclass_of("BaseRepository")]
""",
            path="pkg_c/repository.py",
        ),
    ]

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert len(rules) == 1
    assert rules[0].rule_type == "compiler_invalid_param"
    assert rules[0].params["decorator"] == "not_subclass_of"
    assert rules[0].params["param"] == "base"
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_base_reference"]
    assert evidence[0].payload["reason"] == "ambiguous_simple_name"


def test_nom001_not_subclass_of_invalid_target_sentinel_rule_evaluates_failed() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import not_subclass_of

def build() -> None:
    __archtest__: Annotated[None, not_subclass_of("source_module.BaseRepository")]
"""
    target = """
def build() -> None:
    return None
"""
    source_entities = _extract_entities(source, path="source_module.py")
    target_entities = _extract_entities(target, path="target_module.py")

    source_func = next(
        e for e in source_entities if e.kind == "function" and e.name == "build"
    )
    target_func = next(
        e for e in target_entities if e.kind == "function" and e.name == "build"
    )

    rules, _, _ = compile_rules(source_entities, Mock())
    sentinel_rules = [r for r in rules if r.rule_type == "compiler_invalid_param"]
    assert len(sentinel_rules) == 1
    assert sentinel_rules[0].rule_id.startswith(
        "NOM001/not_subclass_of/invalid_declaration/"
    )

    matches: dict[str, MatchResult] = {
        source_func.canonical_id: MatchResult(
            source_id=source_func.canonical_id,
            status=MatchStatus.MATCHED,
            target_id=target_func.canonical_id,
            confidence=1.0,
            reasons=[],
            candidates=[],
        ),
    }

    results, errors = evaluate_rules_for_target(
        rules=sentinel_rules,
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches=matches,
        config=Mock(),
        source_by_id={e.canonical_id: e for e in source_entities},
        target_by_id={e.canonical_id: e for e in target_entities},
    )

    assert errors == []
    assert [r.status for r in results] == ["FAILED"]
