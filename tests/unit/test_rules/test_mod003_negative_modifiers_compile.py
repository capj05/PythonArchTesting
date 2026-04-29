from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.entities import Entity
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.rules import (
    is_non_abstract_method,
    is_non_final_class,
    is_non_final_method,
)
from pythonarchtesting.rules.compilation import compile_rules


def _extract_entities(source_text: str) -> list[Entity]:
    return extract_entities_from_source(
        source_text=source_text,
        file_path=Path("source_module.py"),
        root_path=Path("."),
        target_module_name=None,
        role="source",  # type: ignore[arg-type]
        include_nested_functions=False,
        root_label="source",
    )


def _compile_source(source_text: str) -> tuple[list[object], list[object], list[object]]:
    return compile_rules(_extract_entities(source_text), Mock())


def test_mod003_import_surface_exposes_negative_modifier_markers() -> None:
    non_final_class_marker = is_non_final_class()
    non_abstract_marker = is_non_abstract_method(severity="warning")
    non_final_method_marker = is_non_final_method(message="must not be final")

    assert non_final_class_marker.kind == "is_non_final_class"
    assert non_abstract_marker.kind == "is_non_abstract_method"
    assert non_abstract_marker.params["severity"] == "warning"
    assert non_final_method_marker.kind == "is_non_final_method"
    assert non_final_method_marker.message == "must not be final"


def test_mod003_non_final_class_compiles() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_class

class Contract:
    __archtest__: Annotated[None, is_non_final_class()]
"""

    rules, evidence, errors = _compile_source(source)

    assert errors == []
    assert evidence == []
    assert len(rules) == 1
    rule = rules[0]
    assert rule.rule_id == "MOD003/is_non_final_class/v1"
    assert rule.rule_type == "python_modifier"
    assert rule.scope == "class"
    assert rule.params == {
        "modifier_kind": "non_final_class",
        "modifier_polarity": "negative",
        "fail_on_unmatched": True,
    }


def test_mod003_non_abstract_method_compiles() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_abstract_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_abstract_method()]
        return ""
"""

    rules, evidence, errors = _compile_source(source)

    assert errors == []
    assert evidence == []
    assert len(rules) == 1
    rule = rules[0]
    assert rule.rule_id == "MOD003/is_non_abstract_method/v1"
    assert rule.rule_type == "python_modifier"
    assert rule.scope == "method"
    assert rule.params == {
        "modifier_kind": "non_abstract_method",
        "modifier_polarity": "negative",
        "fail_on_unmatched": True,
    }


def test_mod003_non_final_method_compiles() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_final_method()]
        return ""
"""

    rules, evidence, errors = _compile_source(source)

    assert errors == []
    assert evidence == []
    assert len(rules) == 1
    rule = rules[0]
    assert rule.rule_id == "MOD003/is_non_final_method/v1"
    assert rule.rule_type == "python_modifier"
    assert rule.scope == "method"
    assert rule.params == {
        "modifier_kind": "non_final_method",
        "modifier_polarity": "negative",
        "fail_on_unmatched": True,
    }


def test_mod003_non_final_class_rejects_method_placement() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_class

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_non_final_class()]
        return ""
"""

    rules, evidence, errors = _compile_source(source)

    assert errors == []
    assert rules == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]
    assert evidence[0].payload["expected_kind"] == "class"
    assert evidence[0].payload["found_kind"] == "method"


def test_mod003_non_abstract_method_rejects_class_placement() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_abstract_method

class Contract:
    __archtest__: Annotated[None, is_non_abstract_method()]
"""

    rules, evidence, errors = _compile_source(source)

    assert errors == []
    assert rules == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]
    assert evidence[0].payload["expected_kind"] == "method"
    assert evidence[0].payload["found_kind"] == "class"


def test_mod003_non_final_method_rejects_function_placement() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_non_final_method

def helper() -> None:
    __archtest__: Annotated[None, is_non_final_method()]
"""

    rules, evidence, errors = _compile_source(source)

    assert errors == []
    assert rules == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]
    assert evidence[0].payload["expected_kind"] == "method"
    assert evidence[0].payload["found_kind"] == "function"
