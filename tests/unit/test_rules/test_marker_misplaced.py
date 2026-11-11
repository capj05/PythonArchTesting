"""A marker declared where it checks nothing makes its declaration invalid.

A marker on an entity of a kind it does not check (``is_enum`` on a function,
``required_method`` on a class), or ``enforce_layers`` / ``forbid_cycles``
outside the root module, used to leave only compiler evidence: the marker
disappeared from the report. Every such declaration now also gives a
``compiler_invalid_param`` sentinel rule for ``target_kind`` under the
marker's prefix for invalid declarations, so the mistake shows as FAILED;
the evidence is the one reported before.

Each declaration of the package of :mod:`test_marker_invalid_severity` is
declared again on a module that is not the root, on a class and on a
function, so that every marker lands on at least one place it does not check.
"""

from __future__ import annotations

import ast
from typing import Any

import pytest

from pythonarchtesting.config.loader import load_config
from pythonarchtesting.rules.compilation import compile_rules
from pythonarchtesting.runner.source_prep import prepare_source
from tests.unit.test_rules import test_marker_invalid_severity as package

_PLACEMENT_ISSUES = {"compiler_invalid_target"}


def _declarations() -> dict[str, str]:
    """Marker name -> the source of its first declaration in the package."""
    found: dict[str, str] = {}
    for source in (package._INIT, package._APP):
        for node in ast.walk(ast.parse(source)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in package.MARKERS
            ):
                found.setdefault(node.func.id, ast.get_source_segment(source, node))
    return found


def _host(header: str, calls: list[str], indent: str) -> str:
    body = ",\n".join(f"{indent}    {call}" for call in calls)
    return f"{header}{indent}__archtest__: Annotated[\n{indent}    None,\n{body},\n{indent}]\n"


@pytest.fixture(scope="module")
def misplaced(tmp_path_factory: pytest.TempPathFactory) -> tuple[list[Any], list[Any]]:
    calls = sorted(_declarations().values())
    names = sorted(_declarations())
    elsewhere = (
        "from typing import Annotated\n"
        f"from pythonarchtesting.rules import {', '.join(names)}\n\n"
        + _host("", calls, "")
        + "\n\nclass Port:\n    pass\n\n\nclass Holder:\n"
        + _host("", calls, "    ")
        + "\n\ndef helper(value: int) -> int:\n"
        + _host("", calls, "    ")
        + "    return value\n"
    )
    root = tmp_path_factory.mktemp("misplaced") / "pkg"
    root.mkdir()
    for name, text in (
        ("__init__.py", ""),
        ("models.py", package._MODELS),
        ("app.py", "class Service:\n    pass\n"),
        ("elsewhere.py", elsewhere),
    ):
        (root / name).write_text(text.replace("SEV", '"error"'), encoding="utf-8")
    state = prepare_source(config=load_config(), source_path=root)
    rules, evidence, _ = compile_rules(list(state.source_entities), load_config())
    return rules, evidence


def _marker(item: Any) -> str:
    return item.payload.get("declaration", item.payload.get("decorator"))


def test_every_misplaced_declaration_gives_a_target_kind_sentinel(
    misplaced: tuple[list[Any], list[Any]],
) -> None:
    rules, evidence = misplaced
    reported = sorted(
        (item.entity_id, _marker(item))
        for item in evidence
        if item.payload.get("issue") in _PLACEMENT_ISSUES
    )
    sentinels = sorted(
        (rule.selector.source_entity_id, rule.name)
        for rule in rules
        if rule.rule_type == "compiler_invalid_param"
        and rule.params["param"] == "target_kind"
    )

    assert reported == sentinels


def test_every_marker_is_misplaced_somewhere(
    misplaced: tuple[list[Any], list[Any]],
) -> None:
    rules, _ = misplaced
    misplaced_markers = {
        rule.name
        for rule in rules
        if rule.rule_type == "compiler_invalid_param"
        and rule.params["param"] == "target_kind"
    }
    # Markers every place of the package is valid for.
    anywhere = {"forbid_imports", "required_entity_signature"}

    assert misplaced_markers == set(package.MARKERS) - anywhere


@pytest.mark.parametrize("marker", ["enforce_layers", "forbid_cycles"])
def test_a_root_marker_outside_the_root_module_is_invalid(
    misplaced: tuple[list[Any], list[Any]], marker: str
) -> None:
    rules, _ = misplaced
    sentinels = [
        rule
        for rule in rules
        if rule.name == marker
        and rule.selector.source_entity_id.endswith(":elsewhere:module:-")
        and rule.rule_type == "compiler_invalid_param"
    ]

    assert [rule.params["valid"] for rule in sentinels] == [["root module"]]
    assert sentinels[0].params["compiler_reason"] == (
        f"{marker} must be declared on the root module (__init__.py)"
    )
