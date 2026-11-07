"""Review of the N5 fix round: the strategy task on variants of its reference.

- a strategy class the context builds that the reference does not have (a
  renamed ``PercentOff``, a new ``HalfPrice``, a subclass ``TenPercent``) is
  ``hardcoded_strategy``, while a matched class no role binds stays allowed,
  and so does a class of its own in the strategies' module that is no
  strategy (a value, a dataclass, an exception; N7 review);
- a role that binds only the interface (``discounts.Discount``) forbids
  building the classes that implement it;
- correct code that displays ``type(...)``, builds ``type(self)(...)`` or
  checks against ``type(None)`` passes, and a reference doing so is accepted;
- an if-chain on the kind of strategy is one error, not two.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from pythonarchtesting.mcp_server.evaluation import run_evaluation
from pythonarchtesting.mcp_server.reports import explain_target
from pythonarchtesting.mcp_server.tasks import prepare_task

_TASK = Path(__file__).resolve().parents[2] / "example" / "principles" / "strategy"
_INIT = "        self.discount = discount\n"
_TOTAL = "        amount = sum(prices)\n"

# name -> {file: [(old, new), ...]} applied to the reference.
_VARIANTS: dict[str, dict[str, list[tuple[str, str]]]] = {
    "ok_percent_log": {
        "pricing.py": [
            (
                _TOTAL,
                _TOTAL + '        self.last = "discount: %s" % '
                "type(self.discount).__name__\n",
            )
        ]
    },
    "ok_type_none": {
        "pricing.py": [
            (
                _TOTAL,
                "        if not all(isinstance(p, (int, float, type(None))) "
                'for p in prices):\n            raise TypeError("bad price")\n'
                + _TOTAL,
            )
        ]
    },
    "ok_type_self": {
        "pricing.py": [
            (
                _TOTAL,
                _TOTAL + "        self.copy = type(self)(self.discount) "
                "if amount < 0 else None\n",
            )
        ]
    },
    # A class of its own in the context's module, no strategy: allowed.
    "ok_builds_a_log": {
        "pricing.py": [
            (
                "class PriceCalculator:",
                "class Log:\n    pass\n\n\nclass PriceCalculator:",
            ),
            (_INIT, _INIT + "        self.log = Log()\n"),
        ],
    },
    "err_new_class": {
        "discounts.py": [
            (
                "class NoDiscount:",
                "class HalfPrice:\n    def apply(self, amount: float) -> float:\n"
                "        return amount / 2\n\n\nclass NoDiscount:",
            )
        ],
        "pricing.py": [
            (
                "from .discounts import Discount",
                "from .discounts import Discount, HalfPrice",
            ),
            (_INIT, "        self.discount = HalfPrice()\n"),
        ],
    },
    # Classes of its own in the strategies' module that the context builds
    # but that are no strategy: no base the task binds, no method of a
    # strategy's (``apply``), or an exception whatever its methods.
    "ok_value_in_discounts": {
        "discounts.py": [
            (
                "class NoDiscount:",
                "class Money:\n    def __init__(self, amount):\n"
                "        self.amount = amount\n\n    def rounded(self):\n"
                "        return round(self.amount, 2)\n\n\nclass NoDiscount:",
            )
        ],
        "pricing.py": [
            (
                "from .discounts import Discount",
                "from .discounts import Discount, Money",
            ),
            (_TOTAL, _TOTAL + "        self.last = Money(amount)\n"),
        ],
    },
    "ok_dataclass_in_discounts": {
        "discounts.py": [
            (
                "from typing import Protocol\n",
                "from dataclasses import dataclass\nfrom typing import Protocol\n",
            ),
            (
                "class NoDiscount:",
                "@dataclass\nclass Receipt:\n    amount: float\n\n\n"
                "class NoDiscount:",
            ),
        ],
        "pricing.py": [
            (
                "from .discounts import Discount",
                "from .discounts import Discount, Receipt",
            ),
            (_TOTAL, _TOTAL + "        self.last = Receipt(amount)\n"),
        ],
    },
    "ok_error_in_discounts": {
        "discounts.py": [
            (
                "class NoDiscount:",
                "class DiscountError(ValueError):\n"
                "    def apply(self, amount: float) -> float:\n"
                "        return amount\n\n\nclass NoDiscount:",
            )
        ],
        "pricing.py": [
            (
                "from .discounts import Discount",
                "from .discounts import Discount, DiscountError",
            ),
            (_TOTAL, _TOTAL + '        self.last = DiscountError("none")\n'),
        ],
    },
    # A class of its own that only inherits a strategy: still a strategy.
    "err_subclass": {
        "discounts.py": [
            (
                "class BulkDiscount:",
                "class TenPercent(PercentDiscount):\n"
                "    def __init__(self) -> None:\n"
                "        super().__init__(10)\n\n\nclass BulkDiscount:",
            )
        ],
        "pricing.py": [
            (
                "from .discounts import Discount",
                "from .discounts import Discount, TenPercent",
            ),
            (_INIT, "        self.discount = TenPercent()\n"),
        ],
    },
    "err_renamed": {
        "discounts.py": [("class PercentDiscount:", "class PercentOff:")],
        "app.py": [("PercentDiscount", "PercentOff")],
        "pricing.py": [
            (
                "from .discounts import Discount",
                "from .discounts import Discount, PercentOff",
            ),
            (_INIT, "        self.discount = PercentOff(10)\n"),
        ],
    },
}


def _variant(root: Path, name: str) -> Path:
    target = root / name
    shutil.copytree(_TASK / "reference", target)
    for file, changes in _VARIANTS[name].items():
        path = target / file
        text = path.read_text(encoding="utf-8")
        for old, new in changes:
            assert old in text, (name, file, old)
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
    return target


def _findings(task: Path, students: Path, out: Path) -> dict[str, tuple]:
    report = run_evaluation(
        source=str(task),
        output_dir=str(out),
        targets_dir=str(students),
        dynamic=True,
        sandbox="limits",
    )
    found = {}
    for path in sorted(students.iterdir()):
        explained = explain_target(
            report["report_json"], path.name, principle="strategy"
        )
        found[path.name] = (
            explained["verdict"],
            sorted({f["error_id"] for f in explained["findings"]}),
        )
    return found


def test_the_strategy_task_judges_the_reviewed_variants(tmp_path: Path) -> None:
    students = tmp_path / "class"
    for name in _VARIANTS:
        _variant(students, name)

    found = _findings(_TASK, students, tmp_path / "out")

    assert found == {
        "ok_percent_log": ("passed", []),
        "ok_type_none": ("passed", []),
        "ok_type_self": ("passed", []),
        "ok_builds_a_log": ("passed", []),
        "ok_value_in_discounts": ("passed", []),
        "ok_dataclass_in_discounts": ("passed", []),
        "ok_error_in_discounts": ("passed", []),
        "err_new_class": ("failed", ["hardcoded_strategy"]),
        "err_subclass": ("failed", ["hardcoded_strategy"]),
        "err_renamed": ("failed", ["hardcoded_strategy"]),
    }


def test_an_if_chain_on_the_kind_of_strategy_is_one_error(tmp_path: Path) -> None:
    students = tmp_path / "class"
    shutil.copytree(_TASK / "assignments" / "err_total_if_chain", students / "chain")

    found = _findings(_TASK, students, tmp_path / "out")

    assert found == {"chain": ("failed", ["type_switch_on_strategy"])}


def test_each_error_example_is_classified_as_that_error_alone(
    tmp_path: Path,
) -> None:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        tomllib = pytest.importorskip("tomli")
    examples = tomllib.loads((_TASK / "principle.toml").read_text(encoding="utf-8"))[
        "examples"
    ]
    students = tmp_path / "class"
    errors = ("no_delegation", "hardcoded_strategy", "type_switch_on_strategy")
    for error in errors:
        shutil.copytree(_TASK / "assignments" / examples[error], students / error)

    found = _findings(_TASK, students, tmp_path / "out")

    assert found == {error: ("failed", [error]) for error in errors}


def _task_copy(root: Path, roles: str | None = None) -> Path:
    task = root / "task"
    shutil.copytree(_TASK / "reference", task / "reference")
    text = (_TASK / "task.toml").read_text(encoding="utf-8")
    if roles is not None:
        start = text.index("strategy = [")
        end = text.index("]", start) + 1
        text = text[:start] + roles + text[end:]
    (task / "task.toml").write_text(text, encoding="utf-8")
    return task


def test_binding_the_interface_forbids_building_its_implementations(
    tmp_path: Path,
) -> None:
    task = _task_copy(tmp_path, 'strategy = ["discounts.Discount"]')
    students = tmp_path / "class"
    shutil.copytree(
        _TASK / "assignments" / "err_calculator_builds_discount", students / "builds"
    )
    shutil.copytree(_TASK / "assignments" / "ok_basic", students / "ok")

    prepared = prepare_task(str(task), sandbox="limits")
    found = _findings(task, students, tmp_path / "out")

    assert prepared["accepted"] is True, prepared
    assert {e["error"]: e["status"] for e in prepared["errors"]}[
        "hardcoded_strategy"
    ] == "killed"
    assert found == {
        "builds": ("failed", ["hardcoded_strategy"]),
        "ok": ("passed", []),
    }


@pytest.mark.parametrize("variant", ["ok_percent_log", "ok_type_self"])
def test_a_reference_that_displays_or_builds_by_type_is_accepted(
    tmp_path: Path, variant: str
) -> None:
    task = _task_copy(tmp_path)
    shutil.rmtree(task / "reference")
    shutil.copytree(_variant(tmp_path / "v", variant), task / "reference")

    prepared = prepare_task(str(task), sandbox="limits")

    assert prepared["problems"] == [], prepared
    assert prepared["accepted"] is True, prepared
