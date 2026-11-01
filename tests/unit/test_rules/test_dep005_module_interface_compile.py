"""Compiling ``module_interface`` (DEP005, DYN012)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pythonarchtesting.config.loader import load_config
from pythonarchtesting.runner.source_prep import prepare_source

_MODULES = {
    "__init__.py": "",
    "controller.py": "def handle(request, service):\n    return service.run()\n",
    "service.py": "class Service:\n    def run(self):\n        return 1\n",
    "models.py": "class Order:\n    pass\n\n\ndef _helper():\n    return 0\n",
}
_HEADER = (
    "from typing import Annotated\n"
    "from pythonarchtesting.rules import module_interface\n\n"
)


def _rules(tmp_path: Path, markers: str, where: str = "models.py") -> list:
    root = tmp_path / "reference"
    root.mkdir()
    for name, text in _MODULES.items():
        (root / name).write_text(text, encoding="utf-8")
    target = root / where
    target.write_text(
        _HEADER
        + target.read_text(encoding="utf-8")
        + f"\n__archtest__: Annotated[None, {markers}]\n",
        encoding="utf-8",
    )
    state = prepare_source(config=load_config(), source_path=root)
    return [rule for rule in state.rules if "module_interface" in rule.rule_id]


def test_without_names_the_public_names_are_the_interface(tmp_path: Path):
    (rule,) = _rules(tmp_path, "module_interface()")

    assert rule.rule_id == "DEP005/module_interface/v1"
    assert rule.rule_type == "module_interface"
    assert rule.params["names"] == []
    assert rule.params["module"] == "models"
    assert ":models:models:module:" in rule.selector.source_entity_id


def test_named_interface_and_runtime_part(tmp_path: Path):
    rules = _rules(
        tmp_path,
        'module_interface("Order", entry="controller.handle", '
        'cases=[{"args": [{}, {"$new": "service.Service"}]}])',
    )

    static, runtime = sorted(rules, key=lambda rule: rule.rule_id)
    assert static.params["names"] == ["Order"]
    assert runtime.rule_id == "DYN012/module_interface/v1"
    assert runtime.rule_type == "runtime_module_interface"
    assert runtime.params["module"] == "models"
    assert runtime.params["entry"] == "controller.handle"


@pytest.mark.parametrize(
    ("markers", "param", "reason"),
    [
        ('module_interface("Nowhere")', "names", "Nowhere"),
        (
            'module_interface("Order", entry="controller.missing", cases=[{"args": []}])',
            "entry",
            "no function",
        ),
    ],
)
def test_invalid_declarations(tmp_path: Path, markers: str, param: str, reason: str):
    (rule,) = _rules(tmp_path, markers)

    assert rule.rule_type == "compiler_invalid_param"
    assert rule.params["param"] == param
    assert reason in rule.params["compiler_reason"]


def test_constants_imports_and_submodules_are_names(tmp_path: Path):
    root = tmp_path / "reference"
    (root / "sales").mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "sales" / "orders.py").write_text(
        "def place_order():\n    return 1\n", encoding="utf-8"
    )
    (root / "sales" / "__init__.py").write_text(
        _HEADER
        + "from .orders import place_order\nMAX = 3\n"
        + '__archtest__: Annotated[None, module_interface("place_order", "MAX", "orders")]\n',
        encoding="utf-8",
    )

    state = prepare_source(config=load_config(), source_path=root)
    (rule,) = [r for r in state.rules if "module_interface" in r.rule_id]

    assert rule.rule_id == "DEP005/module_interface/v1"
