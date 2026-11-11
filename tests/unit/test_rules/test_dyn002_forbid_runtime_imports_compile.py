from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import Mock

import pytest

from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.rules.compilation import compile_rules


def _compile(source: str) -> tuple[list, list, list]:
    entities = extract_entities_from_source(
        textwrap.dedent(source).strip() + "\n",
        Path("source_module.py"),
        Path("."),
        None,
        role="source",
        include_nested_functions=False,
        root_label="source",
    )
    return compile_rules(entities, Mock())


def test_dyn002_compile_emits_runtime_imports_rule() -> None:
    rules, evidence, compiler_results = _compile("""
from typing import Annotated
from pythonarchtesting.rules import forbid_runtime_imports

__archtest__: Annotated[
    None,
    forbid_runtime_imports("sqlite3", "xml", "sqlite3", allow=["xml.sax"]),
]
""")

    assert evidence == []
    assert compiler_results == []
    assert [rule.rule_id for rule in rules] == ["DYN002/forbid_runtime_imports/v1"]
    rule = rules[0]
    assert rule.rule_type == "runtime_imports"
    assert rule.evidence_type == "runtime"
    assert rule.params["forbidden"] == ["sqlite3", "xml"]
    assert rule.params["allow"] == ["xml.sax"]
    assert rule.params["timeout_s"] == 5.0


def test_dyn002_compile_on_function_emits_invalid_target_evidence() -> None:
    rules, evidence, _ = _compile("""
from typing import Annotated
from pythonarchtesting.rules import forbid_runtime_imports

def build() -> None:
    __archtest__: Annotated[None, forbid_runtime_imports("sqlite3")]
""")

    # The misplaced marker is a FAILED sentinel, not missing from the report.
    assert [(rule.rule_type, rule.params["param"]) for rule in rules] == [
        ("compiler_invalid_param", "target_kind")
    ]
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


@pytest.mark.parametrize(
    ("marker", "param"),
    [
        ("forbid_runtime_imports()", "forbidden"),
        ('forbid_runtime_imports("sqlite3", timeout_s=-1)', "timeout_s"),
    ],
)
def test_dyn002_compile_rejects_invalid_params_with_a_sentinel(
    marker: str, param: str
) -> None:
    rules, evidence, _ = _compile(f"""
from typing import Annotated
from pythonarchtesting.rules import forbid_runtime_imports

__archtest__: Annotated[None, {marker}]
""")

    assert [rule.rule_type for rule in rules] == ["compiler_invalid_param"]
    assert rules[0].params["param"] == param
    assert [item.type for item in evidence] == ["compiler_invalid_param"]


def test_dyn002_compile_accepts_an_explicit_none_allow_list() -> None:
    rules, evidence, _ = _compile("""
from typing import Annotated
from pythonarchtesting.rules import forbid_runtime_imports

__archtest__: Annotated[None, forbid_runtime_imports("sqlite3", allow=None)]
""")

    assert evidence == []
    assert [rule.rule_id for rule in rules] == ["DYN002/forbid_runtime_imports/v1"]
    assert rules[0].params["allow"] == []
