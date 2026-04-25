from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.entities import Entity
from pythonarchtesting.entities_extraction import extract_entities_from_source
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


def test_enum001_compile_emits_enum_type_rule() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_enum

class StatusContract:
    __archtest__: Annotated[None, is_enum()]
"""

    source_entities = _extract_entities(source, path="source_module.py")
    source_entity = next(
        entity
        for entity in source_entities
        if entity.kind == "class" and entity.name == "StatusContract"
    )

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert evidence == []
    assert compiler_results == []
    compiled_rules = [
        rule
        for rule in rules
        if rule.selector.source_entity_id == source_entity.canonical_id
    ]
    assert [rule.rule_id for rule in compiled_rules] == ["ENUM001/is_enum/v1"]
    assert compiled_rules[0].rule_type == "enum_type"
    assert compiled_rules[0].name == "is_enum"
    assert compiled_rules[0].params["fail_on_unmatched"] is True


def test_enum001_compile_non_class_emits_invalid_target_evidence() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_enum

def build() -> None:
    __archtest__: Annotated[None, is_enum()]
"""

    source_entities = _extract_entities(source, path="source_module.py")

    rules, evidence, compiler_results = compile_rules(source_entities, Mock())

    assert rules == []
    assert compiler_results == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]
