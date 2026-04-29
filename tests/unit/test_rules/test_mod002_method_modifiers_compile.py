from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from pythonarchtesting.entities import Entity
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.rules import is_abstract_method, is_final_method
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


def test_mod002_import_surface_exposes_method_modifier_markers() -> None:
    abstract_marker = is_abstract_method()
    final_marker = is_final_method(severity="warning", message="final required")

    assert abstract_marker.kind == "is_abstract_method"
    assert final_marker.kind == "is_final_method"
    assert final_marker.params["severity"] == "warning"
    assert final_marker.message == "final required"


def test_mod002_abstract_method_compiles() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_method

class Contract:
    def render(self) -> str:
        __archtest__: Annotated[None, is_abstract_method()]
        raise NotImplementedError
"""

    rules, evidence, errors = _compile_source(source)

    assert errors == []
    assert evidence == []
    assert len(rules) == 1
    rule = rules[0]
    assert rule.rule_id == "MOD002/is_abstract_method/v1"
    assert rule.rule_type == "python_modifier"
    assert rule.scope == "method"
    assert rule.params == {
        "modifier_kind": "abstract_method",
        "modifier_polarity": "positive",
        "fail_on_unmatched": True,
    }


def test_mod002_final_method_compiles() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_final_method

class Contract:
    def close(self) -> None:
        __archtest__: Annotated[None, is_final_method()]
        return None
"""

    rules, evidence, errors = _compile_source(source)

    assert errors == []
    assert evidence == []
    assert len(rules) == 1
    rule = rules[0]
    assert rule.rule_id == "MOD002/is_final_method/v1"
    assert rule.rule_type == "python_modifier"
    assert rule.scope == "method"
    assert rule.params == {
        "modifier_kind": "final_method",
        "modifier_polarity": "positive",
        "fail_on_unmatched": True,
    }


def test_mod002_abstract_method_rejects_class_placement() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_abstract_method

class Contract:
    __archtest__: Annotated[None, is_abstract_method()]
"""

    rules, evidence, errors = _compile_source(source)

    assert errors == []
    assert rules == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]
    assert evidence[0].payload["expected_kind"] == "method"
    assert evidence[0].payload["found_kind"] == "class"


def test_mod002_final_method_rejects_function_placement() -> None:
    source = """
from typing import Annotated
from pythonarchtesting.rules import is_final_method

def helper() -> None:
    __archtest__: Annotated[None, is_final_method()]
"""

    rules, evidence, errors = _compile_source(source)

    assert errors == []
    assert rules == []
    assert [item.type for item in evidence] == ["compiler_invalid_target"]
    assert evidence[0].payload["expected_kind"] == "method"
    assert evidence[0].payload["found_kind"] == "function"
