"""Facts of the markers a typical error of ``polymorphism`` and ``strategy``
is detected by: one fact per violation, in the same order (``details.facts``
aligned 1:1 with ``details.violations``), so that ``classify`` can match each
violation to a catalogue error.

The static markers (``subclass_of``, ``is_abstract_class``) run through the
CLI on a reference and a submission; the runtime ones
(``forbid_runtime_instantiation``, ``require_runtime_delegation``) judge a
probe outcome placed in the batch cache.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pythonarchtesting.cli import main

from .test_dynamic_evaluators import _cases
from .test_dynamic_evaluators import _evaluate as _evaluate_structure
from .test_dynamic_evaluators import _instance, _rule_and_entity
from .test_dynamic_pattern_evaluators import _evaluate as _evaluate_pattern

_HEADER = (
    "from typing import Annotated\n"
    "from pythonarchtesting.rules import is_abstract_class, subclass_of\n\n\n"
)

_REFERENCE = (
    _HEADER + "from abc import ABC, abstractmethod\n\n\n"
    "class Shape(ABC):\n"
    "    __archtest__: Annotated[None, is_abstract_class()]\n\n"
    "    @abstractmethod\n"
    "    def area(self):\n"
    "        raise NotImplementedError\n\n\n"
    "class Circle(Shape):\n"
    '    __archtest__: Annotated[None, subclass_of("Shape")]\n\n'
    "    def area(self):\n"
    "        return 3\n\n\n"
    "class Square(Shape):\n"
    '    __archtest__: Annotated[None, subclass_of("Shape")]\n\n'
    "    def area(self):\n"
    "        return 4\n"
)

# The base is concrete and neither variant derives from it.
_SUBMISSION = (
    "class Shape:\n"
    "    def area(self):\n"
    "        return 0\n\n"
    "    def describe(self):\n"
    "        return 'shape'\n\n\n"
    "class Circle:\n"
    "    def area(self):\n"
    "        return 3\n\n\n"
    "class Square:\n"
    "    def area(self):\n"
    "        return 4\n"
)


def _write(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True)
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def _static_results(tmp_path: Path, prefix: str) -> list[dict[str, Any]]:
    source = _write(
        tmp_path / "reference", {"__init__.py": "", "shapes.py": _REFERENCE}
    )
    submission = _write(
        tmp_path / "target", {"__init__.py": "", "shapes.py": _SUBMISSION}
    )
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(source),
            "--target",
            str(submission),
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    return [
        r
        for t in report["targets"]
        for r in t["results"]
        if str(r["rule_id"]).startswith(prefix)
    ]


def _aligned(details: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    facts, texts = details["facts"], details["violations"]
    assert len(facts) == len(texts)
    return list(zip(facts, texts))


def test_subclass_of_facts_aligned_with_violations(tmp_path: Path) -> None:
    results = _static_results(tmp_path, "NOM001/subclass_of/")

    assert [r["status"] for r in results] == ["FAILED", "FAILED"]
    facts = []
    for result in results:
        [(fact, text)] = _aligned(result["details"])
        assert f"{fact['class']} " in text and fact["expected_base"] in text
        assert f"{fact['file']}:{fact['line']}" in text
        facts.append(fact)
    assert sorted(facts, key=lambda f: f["line"]) == [
        {
            "kind": "not_subclass",
            "class": "shapes:Circle",
            "expected_base": "shapes:Shape",
            "file": "shapes.py",
            "line": 9,
        },
        {
            "kind": "not_subclass",
            "class": "shapes:Square",
            "expected_base": "shapes:Shape",
            "file": "shapes.py",
            "line": 14,
        },
    ]


def test_is_abstract_class_facts_aligned_with_violations(tmp_path: Path) -> None:
    [result] = _static_results(tmp_path, "MOD001/is_abstract_class/")

    assert result["status"] == "FAILED"
    [(fact, text)] = _aligned(result["details"])
    assert fact == {
        "kind": "not_abstract",
        "class": "shapes:Shape",
        "concrete_methods": ["area", "describe"],
        "file": "shapes.py",
        "line": 1,
    }
    assert "shapes:Shape" in text and "shapes.py:1" in text


def test_passing_static_markers_have_no_facts(tmp_path: Path) -> None:
    source = _write(
        tmp_path / "reference", {"__init__.py": "", "shapes.py": _REFERENCE}
    )
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(source),
            "--target",
            str(source),
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    results = [r for t in report["targets"] for r in t["results"]]
    assert {r["status"] for r in results} == {"OK"}
    assert not any("facts" in r["details"] for r in results)


_INSTANTIATION = (
    'forbid_runtime_instantiation("repository", transitive=True, cases=[{}, {}])'
)


def test_forbid_runtime_instantiation_facts_aligned_with_violations() -> None:
    _, entity = _rule_and_entity(_INSTANTIATION)
    own = entity.module_path
    detour = {
        **_instance("repository", "helpers", "Cache", 12),
        "origin": {"from": own, "caller": "handle", "line": 6},
        "via": [{"module": "helpers", "caller": "build"}],
    }
    result = _evaluate_structure(
        _INSTANTIATION,
        _cases(
            {
                "instances": [
                    _instance("repository", own, "Repo", 4),
                    _instance("domain", own, "Order", 5),
                    _instance("repository.sql", own, "SqlRepo", 9),
                ]
            },
            {"instances": [detour]},
        ),
    )

    assert result.status == "FAILED"
    pairs = _aligned(result.details)
    assert [fact for fact, _ in pairs] == [
        {
            "kind": "instance",
            "case": 0,
            "creator": f"{own}:handle",
            "class": "repository:Repo",
            "file": f"{own}.py",
            "line": 4,
            "via": [],
        },
        {
            "kind": "instance",
            "case": 0,
            "creator": f"{own}:handle",
            "class": "repository.sql:SqlRepo",
            "file": f"{own}.py",
            "line": 9,
            "via": [],
        },
        {
            "kind": "instance",
            "case": 1,
            "creator": f"{own}:handle",
            "class": "repository:Cache",
            "file": "helpers.py",
            "line": 12,
            "via": ["helpers:build"],
        },
    ]
    for fact, text in pairs:
        assert text.startswith(f"case {fact['case']}: ")
        assert f"{fact['class']} at {fact['file']}:{fact['line']}" in text


_DELEGATION = (
    'require_runtime_delegation("strategy", member="apply", '
    'cases=[{"args": [{"$spy": "strategy"}]}, {"args": [{"$spy": "strategy"}]}])'
)


def test_require_runtime_delegation_facts_aligned_with_violations() -> None:
    result = _evaluate_pattern(
        _DELEGATION,
        _cases(
            {"spy_calls": [{"spy": "strategy", "member": "other", "args": 1}]},
            {"spy_calls": [], "raised": "KeyError: 'x'"},
        ),
    )

    assert result.status == "FAILED"
    pairs = _aligned(result.details)
    assert [fact for fact, _ in pairs] == [
        {
            "kind": "missing_delegation",
            "case": 0,
            "caller": "patterns:run",
            "expected": "strategy.apply",
            "raised": None,
        },
        {
            "kind": "missing_delegation",
            "case": 1,
            "caller": "patterns:run",
            "expected": "strategy.apply",
            "raised": "KeyError: 'x'",
        },
    ]
    for fact, text in pairs:
        assert text.startswith(f"case {fact['case']}: never delegated to ")


def test_a_delegating_rule_has_no_facts() -> None:
    result = _evaluate_pattern(
        _DELEGATION,
        _cases(
            {"spy_calls": [{"spy": "strategy", "member": "apply", "args": 1}]},
            {"spy_calls": [{"spy": "strategy", "member": "apply", "args": 1}]},
        ),
    )

    assert result.status == "OK"
    assert "facts" not in result.details


def test_subclass_of_on_the_base_itself_says_so_and_has_no_fact(
    tmp_path: Path,
) -> None:
    reference = _REFERENCE.replace(
        "    __archtest__: Annotated[None, is_abstract_class()]\n",
        '    __archtest__: Annotated[None, subclass_of("Shape")]\n',
    )
    source = _write(tmp_path / "reference", {"__init__.py": "", "shapes.py": reference})
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(source),
            "--target",
            str(source),
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    [result] = [
        r
        for t in report["targets"]
        for r in t["results"]
        if str(r["rule_id"]).startswith("NOM001/subclass_of/") and r["status"] != "OK"
    ]

    assert result["status"] == "FAILED"
    assert "facts" not in result["details"]
    assert result["details"]["violations"] == [
        "shapes:Shape is the base class itself; subclass_of needs a class "
        "derived from it, not the base"
    ]


def test_spy_holder_names_what_the_constructor_stores_the_spy_in() -> None:
    """``{expected}`` names the student's attribute, not the spy (review of
    N5): the spy given as the first argument lands in ``self.discount``."""
    import ast

    from pythonarchtesting.execution.evaluators.runtime_structure import spy_holder

    tree = ast.parse(
        "class Calc:\n"
        "    def __init__(me, rate, discount, *, label=''):\n"
        "        me.rate = rate\n"
        "        me.discount: object = discount\n"
        "        me.label = label\n\n"
        "    def total(me, prices):\n"
        "        return me.discount.apply(sum(prices))\n\n\n"
        "class Bare:\n"
        "    def __init__(self, strategy):\n"
        "        pass\n"
    )
    spy = {"$spy": "strategy"}

    assert spy_holder(tree, "Calc", {"args": [0.2, spy]}, "strategy") == "me.discount"
    assert (
        spy_holder(
            tree, "Calc", {"args": [0.2], "kwargs": {"discount": spy}}, "strategy"
        )
        == "me.discount"
    )
    # Not stored: the parameter; no constructor or no spy: nothing.
    assert spy_holder(tree, "Bare", {"args": [spy]}, "strategy") == "strategy"
    assert spy_holder(tree, "Missing", {"args": [spy]}, "strategy") is None
    assert spy_holder(tree, "Calc", {"args": [0.2, 1]}, "strategy") is None
