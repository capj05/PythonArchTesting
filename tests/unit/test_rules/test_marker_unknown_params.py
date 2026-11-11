"""A keyword argument a marker does not take makes its declaration invalid.

A misspelt keyword (``required_method(declard_only=True)``) used to be
ignored, so the option the author meant was silently left at its default.
Every marker that compiles to a rule now drops such a declaration: a
``compiler_invalid_param`` sentinel rule for the unknown keyword, under the
marker's prefix for invalid declarations, and compiler evidence with the issue
``unknown_param`` naming the keywords the marker takes.

The package of :mod:`test_marker_invalid_severity` declares every marker once;
here each declaration gets one keyword no marker takes.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.rules.declaration import core as declaration_helpers
from tests.unit.test_rules.test_marker_invalid_severity import (
    _DECLARATIONS,
    MARKERS,
    compile_package,
)

_UNKNOWN = "declard_only"


@pytest.fixture(scope="module")
def misspelt(tmp_path_factory: pytest.TempPathFactory) -> tuple[list[Any], list[Any]]:
    return compile_package(
        tmp_path_factory.mktemp("misspelt"), f'"error", {_UNKNOWN}=True'
    )


def _evidence_of(evidence: list[Any], marker: str) -> list[Any]:
    return [
        item
        for item in evidence
        if item.payload.get("decorator", item.payload.get("declaration")) == marker
        and item.payload.get("param") == _UNKNOWN
    ]


@pytest.mark.parametrize("marker", MARKERS)
def test_an_unknown_keyword_drops_the_declaration(
    misspelt: tuple[list[Any], list[Any]], marker: str
) -> None:
    rules, evidence = misspelt
    declarations = _DECLARATIONS.get(marker, 1)
    compiled = [rule for rule in rules if rule.name == marker]

    assert [rule.rule_type for rule in compiled] == [
        "compiler_invalid_param"
    ] * declarations
    takes = [
        name
        for name, param in inspect.signature(
            getattr(declaration_helpers, marker)
        ).parameters.items()
        if param.kind is not inspect.Parameter.VAR_POSITIONAL
    ]
    for sentinel in compiled:
        assert sentinel.rule_id.rsplit("/", 1)[1] == _UNKNOWN
        assert sentinel.params["param"] == _UNKNOWN
        assert sentinel.params["value"] is True
        assert sentinel.params["valid"] == sorted(takes)
        assert sentinel.params["compiler_reason"] == (
            f"unknown parameter {_UNKNOWN!r}; {marker} takes " + ", ".join(takes)
        )
    reported = _evidence_of(evidence, marker)
    assert [item.payload["issue"] for item in reported] == [
        "unknown_param"
    ] * declarations


def test_the_keywords_a_marker_takes_are_no_issue(tmp_path: Path) -> None:
    rules, evidence = compile_package(tmp_path, '"error"')

    assert {rule.rule_type for rule in rules} != {"compiler_invalid_param"}
    assert [item for item in evidence if item.payload.get("issue")] == []
