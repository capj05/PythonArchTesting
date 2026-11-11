"""Compiling ``enforce_layers`` and ``forbid_cycles`` (DEP002, DEP003, DYN009/10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pythonarchtesting.config.loader import load_config
from pythonarchtesting.rules.compilation import compile_rules
from pythonarchtesting.runner.source_prep import prepare_source

_MODULES = {
    "controller.py": "def handle(request, service):\n    return service\n",
    "service.py": "class Service:\n    def run(self):\n        return 1\n",
    "models.py": "class Order:\n    pass\n",
}


def _rules(tmp_path: Path, markers: str, where: str = "__init__.py") -> list:
    root = tmp_path / "reference"
    root.mkdir()
    for name, text in _MODULES.items():
        (root / name).write_text(text, encoding="utf-8")
    header = (
        "from typing import Annotated\n"
        "from pythonarchtesting.rules import enforce_layers, forbid_cycles\n\n"
    )
    target = root / where
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    target.write_text(
        header + existing + f"\n__archtest__: Annotated[None, {markers}]\n",
        encoding="utf-8",
    )
    state = prepare_source(config=load_config(), source_path=root)
    return [
        rule
        for rule in state.rules
        if "layers" in rule.rule_id or "cycles" in rule.rule_id
    ]


def test_layers_compile_to_a_static_rule_on_the_root_module(tmp_path: Path):
    (rule,) = _rules(
        tmp_path,
        'enforce_layers("controller", "service", "models", closed=["service"])',
    )

    assert rule.rule_id == "DEP002/enforce_layers/v1"
    assert rule.rule_type == "module_layers"
    assert rule.evidence_type == "static"
    assert rule.params["layers"] == ["controller", "service", "models"]
    assert rule.params["closed"] == ["service"]
    assert rule.params["fail_on_unmatched"] is True


def test_an_entry_with_cases_adds_a_runtime_rule_on_the_entry(tmp_path: Path):
    rules = _rules(
        tmp_path,
        'forbid_cycles(entry="controller.handle", '
        'cases=[{"args": [{}, {"$new": "service.Service"}]}])',
    )

    static, runtime = sorted(rules, key=lambda rule: rule.rule_id)
    assert static.rule_id == "DEP003/forbid_cycles/v1"
    assert runtime.rule_id == "DYN010/forbid_cycles/v1"
    assert runtime.rule_type == "runtime_cycles"
    assert ":controller:handle:function:" in runtime.selector.source_entity_id
    assert runtime.params["entry"] == "controller.handle"


@pytest.mark.parametrize(
    ("markers", "param", "reason"),
    [
        ('enforce_layers("controller", "nowhere")', "layers", "no module 'nowhere'"),
        ('enforce_layers("controller", "controller")', "layers", "more than one"),
        ('enforce_layers("controller", "models", closed=["x"])', "closed", "no layer"),
        (
            'enforce_layers("controller", "models", closed=["models"])',
            "closed",
            "lowest",
        ),
        (
            'forbid_cycles(entry="controller.missing", cases=[{"args": []}])',
            "entry",
            "no function",
        ),
        ('forbid_cycles(cases=[{"args": []}])', "entry", "need an entry"),
        ('forbid_cycles(entry="controller.handle")', "cases", "non-empty"),
    ],
)
def test_invalid_declarations_become_invalid_param_rules(
    tmp_path: Path, markers: str, param: str, reason: str
):
    (rule,) = _rules(tmp_path, markers)

    assert rule.rule_type == "compiler_invalid_param"
    assert rule.params["param"] == param
    assert reason in rule.params["compiler_reason"]


def test_the_markers_belong_on_a_module(tmp_path: Path):
    root = tmp_path / "reference"
    root.mkdir()
    (root / "controller.py").write_text(
        "from typing import Annotated\n"
        "from pythonarchtesting.rules import forbid_cycles\n\n"
        "def handle():\n"
        "    __archtest__: Annotated[None, forbid_cycles()]  # noqa: F842\n",
        encoding="utf-8",
    )

    state = prepare_source(config=load_config(), source_path=root)
    rules, evidence, _ = compile_rules(list(state.source_by_id.values()), load_config())

    # The misplaced marker is a FAILED sentinel, not missing from the report.
    assert [
        (rule.rule_type, rule.params["param"], rule.params["valid"])
        for rule in rules
        if rule.name == "forbid_cycles"
    ] == [("compiler_invalid_param", "target_kind", ["root module"])]
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


@pytest.mark.parametrize(
    "marker", ['enforce_layers("controller", "models")', "forbid_cycles()"]
)
def test_the_markers_belong_on_the_root_module(tmp_path: Path, marker: str):
    root = tmp_path / "reference"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "models.py").write_text("", encoding="utf-8")
    name = marker.split("(")[0]
    (root / "controller.py").write_text(
        "from typing import Annotated\n"
        f"from pythonarchtesting.rules import {name}\n\n"
        f"__archtest__: Annotated[None, {marker}]\n",
        encoding="utf-8",
    )

    state = prepare_source(config=load_config(), source_path=root)
    rules, evidence, _ = compile_rules(list(state.source_by_id.values()), load_config())

    assert [(rule.rule_type, rule.params["compiler_reason"]) for rule in rules] == [
        (
            "compiler_invalid_param",
            f"{name} must be declared on the root module (__init__.py)",
        )
    ]
    assert [item.type for item in evidence] == ["compiler_invalid_target"]
