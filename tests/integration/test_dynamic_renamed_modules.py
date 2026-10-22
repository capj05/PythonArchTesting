"""Runtime rules on targets that keep a layer in a module of another name.

The markers name the reference's modules; a target that calls its storage
module ``storage`` instead of ``repository`` has the same architecture and
must get the same verdicts.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from pythonarchtesting.cli import main

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHOWCASE = _REPO_ROOT / "example" / "rule_showcase"


def _renamed(family: str, target: str, tmp_path: Path) -> Path:
    """A copy of the showcase target with ``repository.py`` named ``storage.py``."""
    copy = tmp_path / target
    shutil.copytree(_SHOWCASE / family / "assignments" / target, copy)
    (copy / "repository.py").rename(copy / "storage.py")
    for path in copy.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace("from .repository import", "from .storage import"),
            encoding="utf-8",
        )
    return copy


def _verdicts(family: str, target: Path, tmp_path: Path) -> dict[str, tuple]:
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(_SHOWCASE / family / "reference"),
            "--target",
            str(target),
            "--format",
            "json",
            "--output",
            str(output),
            "--dynamic",
        ]
    )
    rows: dict[str, tuple] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if str(node.get("rule_id", "")).startswith(("DYN", "FLW002")) and (
                "status" in node
            ):
                details = node.get("details") or {}
                rows[str(node.get("rule_type")) + ":" + str(node["rule_id"])] = (
                    node["status"],
                    details.get("reason"),
                )
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(output.read_text(encoding="utf-8")))
    return rows


@pytest.fixture(autouse=True)
def _repo_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(_REPO_ROOT)


_REPOSITORY = """
class OrderRepository:
    def get(self, order_id):
        return order_id
"""


def _write(root: Path, files: dict[str, str]) -> Path:
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


@pytest.mark.parametrize("storage", ["repository", "storage"])
def test_importing_the_forbidden_layer_is_caught_under_any_module_name(
    tmp_path: Path, storage: str
) -> None:
    reference = _write(
        tmp_path / "reference",
        {
            "controller.py": (
                "from typing import Annotated\n"
                "from pythonarchtesting.rules import forbid_runtime_imports\n"
                "__archtest__: Annotated[None, forbid_runtime_imports('repository')]\n"
                "def handle(request):\n"
                "    return request\n"
            ),
            "repository.py": _REPOSITORY,
        },
    )
    target = _write(
        tmp_path / "target",
        {
            "controller.py": (
                f"from . import {storage}\n"
                "def handle(request):\n"
                f"    return {storage}.OrderRepository().get(request)\n"
            ),
            f"{storage}.py": _REPOSITORY,
        },
    )
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(reference),
            "--target",
            str(target),
            "--format",
            "json",
            "--output",
            str(output),
            "--dynamic",
        ]
    )
    report = output.read_text(encoding="utf-8")

    assert '"forbidden_import_executed"' in report


def test_a_layered_target_with_a_renamed_storage_module_passes(
    tmp_path: Path,
) -> None:
    target = _renamed("dyn001_layers", "target_pass_basic", tmp_path)

    verdicts = _verdicts("dyn001_layers", target, tmp_path)

    assert verdicts
    assert {status for status, _ in verdicts.values()} == {"OK"}


def test_a_bypass_into_a_renamed_storage_module_is_still_caught(
    tmp_path: Path,
) -> None:
    target = _renamed("dyn001_layers", "target_fail_bypass_service", tmp_path)

    verdicts = _verdicts("dyn001_layers", target, tmp_path)

    assert ("FAILED", "violation") in verdicts.values()
    assert ("OK", "no_violations") in verdicts.values()


def test_the_reference_call_graph_accepts_a_renamed_storage_module(
    tmp_path: Path,
) -> None:
    target = _renamed("dyn001_reference_calls", "target_pass_basic", tmp_path)

    verdicts = _verdicts("dyn001_reference_calls", target, tmp_path)

    assert verdicts
    assert {status for status, _ in verdicts.values()} == {"OK"}


def test_the_reference_call_graph_still_rejects_a_bypass_of_a_renamed_module(
    tmp_path: Path,
) -> None:
    target = _renamed("dyn001_reference_calls", "target_fail_bypass_service", tmp_path)

    verdicts = _verdicts("dyn001_reference_calls", target, tmp_path)

    assert list(verdicts.values()) == [("FAILED", "violation")]


def test_building_an_instance_of_a_renamed_storage_module_is_still_caught(
    tmp_path: Path,
) -> None:
    target = _renamed("dyn004_injection", "target_fail_builds_in_init", tmp_path)

    verdicts = _verdicts("dyn004_injection", target, tmp_path)

    assert ("FAILED", "violation") in verdicts.values()


_ONE_MODULE = """
class OrderRepository:
    def __init__(self):
        self.totals = {}

    def save(self, order_id, total):
        self.totals[order_id] = total

    def get(self, order_id):
        return self.totals.get(order_id)


class Notifier:
    def __init__(self):
        self.sent = []

    def order_placed(self, order_id, total):
        self.sent.append(order_id)


class OrderService:
    def __init__(self, repository, notifier):
        self.repository = repository
        self.notifier = notifier

    def place(self, order_id, prices):
        total = sum(prices)
        self.repository.save(order_id, total)
        self.notifier.order_placed(order_id, total)
        return total


def handle_order(request, service):
    total = service.place(request["id"], request["prices"])
    {bypass}
    return {"status": "ok", "total": total}
"""


@pytest.mark.parametrize(
    ("bypass", "expected", "divergences"),
    [
        ("", [("OK", "no_violations")], []),
        (
            'total = service.repository.get(request["id"])',
            [("FAILED", "violation")],
            ["controller -> repository is not in the reference"],
        ),
    ],
)
def test_layers_kept_in_one_module_are_compared_entity_by_entity(
    tmp_path: Path, bypass: str, expected: list, divergences: list
) -> None:
    # The target keeps every layer in controller.py; the reference's module
    # graph still applies to the classes that play each layer's part.
    target = _write(
        tmp_path / "target", {"controller.py": _ONE_MODULE.replace("{bypass}", bypass)}
    )

    verdicts = _verdicts("dyn001_reference_calls", target, tmp_path)

    assert list(verdicts.values()) == expected
    report = (tmp_path / "report.json").read_text(encoding="utf-8")
    found = sorted(
        set(re.findall(r"case \d+: [a-z_]+ -> [a-z_]+ is not in the reference", report))
    )
    assert [line.split(": ", 1)[1] for line in found] == divergences


_ONE_MODULE_LAYERS = """
class OrderRepository:
    def __init__(self):
        self.totals = {}

    def save(self, order_id, total):
        self.totals[order_id] = total

    def get(self, order_id):
        return self.totals.get(order_id)


class OrderService:
    def __init__(self, repository):
        self.repository = repository

    def place(self, order_id, prices):
        total = sum(prices)
        self.repository.save(order_id, total)
        return total


def handle_order(request, service):
    total = service.place(request["id"], request["prices"])
    {bypass}
    return {"status": "ok", "total": total}
"""


@pytest.mark.parametrize(
    ("bypass", "expected"),
    [
        ("", {("OK", "no_violations")}),
        (
            'total = service.repository.get(request["id"])',
            {("OK", "no_violations"), ("FAILED", "violation")},
        ),
    ],
)
def test_a_direct_call_into_a_layer_kept_in_the_same_module_is_seen(
    tmp_path: Path, bypass: str, expected: set
) -> None:
    target = _write(
        tmp_path / "target",
        {"controller.py": _ONE_MODULE_LAYERS.replace("{bypass}", bypass)},
    )

    verdicts = _verdicts("dyn001_layers", target, tmp_path)

    # require_runtime_calls("service") and forbid_runtime_calls("repository").
    assert set(verdicts.values()) == expected


_CART_REFERENCE = """
from typing import Annotated
from pythonarchtesting.rules import forbid_runtime_calls

from . import store


class Cart:
    def __init__(self, repo):
        self.repo = repo
        self.items = []

    def add_item(self, item):
        self.items.append(item)

    def checkout(self):
        __archtest__: Annotated[None, forbid_runtime_calls(
            "store",
            init={"args": [{"$spy": "repo", "returns": {"prices": {"book": 3}}}]},
            cases=[{"steps": [{"call": "add_item", "args": ["book"]}]}],
        )]
        prices = self.repo.prices()
        return sum(prices[item] for item in self.items)
"""

_CART_TARGET = """
from . import store


class Cart:
    def __init__(self, repo):
        self.repo = repo
        self.items = []

    def add(self, item):
        self.items.append(item)

    def checkout(self):
        prices = self.repo.prices()
        total = sum(prices[item] for item in self.items)
        return store.save(self.items[0], total)
"""

_STORE = "def save(*values):\n    return values\n"


def test_steps_and_spy_answers_reach_a_violation_behind_earlier_calls(
    tmp_path: Path,
) -> None:
    # checkout() needs an item added first and prices from the repository;
    # the target renamed add_item() to add().
    reference = _write(
        tmp_path / "reference", {"cart.py": _CART_REFERENCE, "store.py": _STORE}
    )
    target = _write(tmp_path / "target", {"cart.py": _CART_TARGET, "store.py": _STORE})
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(reference),
            "--target",
            str(target),
            "--format",
            "json",
            "--output",
            str(output),
            "--dynamic",
        ]
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    rows = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if str(node.get("rule_id", "")).startswith("DYN001") and "status" in node:
                rows.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(report)

    assert [(row["status"], row["details"]["reason"]) for row in rows] == [
        ("FAILED", "violation")
    ]
