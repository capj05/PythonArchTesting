"""``enforce_layers`` and ``forbid_cycles`` through the CLI.

Both are declared once, in the reference's root ``__init__.py``. The static
rule judges every import of the target; with ``entry`` and ``cases`` the
runtime rule judges the calls between modules while the entry runs, and only
calls the reference does not make count.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.cli import main

_CASES = (
    '[{"args": [{"id": "A1"}, {"$new": "service.OrderService", '
    '"args": [{"$new": "repository.OrderRepository"}]}]}]'
)

_MARKERS = f"""
from typing import Annotated

from pythonarchtesting.rules import enforce_layers, forbid_cycles

__archtest__: Annotated[
    None,
    enforce_layers(
        "controller", "service", "repository", "models",
        closed=["service"], entry="controller.handle", cases={_CASES},
    ),
    forbid_cycles(entry="controller.handle", cases={_CASES}),
]
"""

_MODELS = """
class Order:
    def __init__(self, order_id):
        self.order_id = order_id
"""

_REPOSITORY = """
class OrderRepository:
    def __init__(self):
        self.saved = []

    def save(self, order):
        self.saved.append(order)
        return order
"""

_SERVICE = """
from .models import Order


class OrderService:
    def __init__(self, repository):
        self.repository = repository

    def place(self, order_id, notify=None):
        order = self.repository.save(Order(order_id))
        if notify is not None:
            notify(order)
        return order
"""

_CONTROLLER = """
def handle(request, service):
    return service.place(request["id"])
"""

_SOLUTION = {
    "models.py": _MODELS,
    "repository.py": _REPOSITORY,
    "service.py": _SERVICE,
    "controller.py": _CONTROLLER,
}

# Each variant changes the solution; the expected statuses are
# (static enforce_layers, static forbid_cycles, runtime enforce_layers,
# runtime forbid_cycles).
_VARIANTS: dict[str, tuple[dict[str, str], tuple[str, str, str, str]]] = {
    "solution": ({}, ("OK", "OK", "OK", "OK")),
    "upward_import": (
        {
            "repository.py": "from . import controller\n" + _REPOSITORY,
        },
        ("FAILED", "OK", "OK", "OK"),
    ),
    "lazy_cycle": (
        {
            "models.py": _MODELS
            + "\n    def describe(self):\n"
            + "        from . import service\n\n"
            + "        return service.__name__\n",
        },
        ("FAILED", "FAILED", "OK", "OK"),
    ),
    "bypass_through_injected_object": (
        {
            "controller.py": "def handle(request, service):\n"
            '    service.repository.save(request["id"])\n'
            '    return service.place(request["id"])\n',
        },
        ("OK", "OK", "FAILED", "OK"),
    ),
    "call_cycle": (
        {
            "repository.py": _REPOSITORY.replace(
                "        self.saved.append(order)\n",
                "        self.saved.append(order.key())\n",
            ),
            "models.py": _MODELS
            + "\n    def key(self):\n"
            + "        return self.order_id\n"
            + "\n    def save_to(self, repository):\n"
            + "        return repository.save(self)\n",
            "service.py": _SERVICE.replace(
                "order = self.repository.save(Order(order_id))",
                "order = Order(order_id).save_to(self.repository)",
            ),
        },
        ("OK", "OK", "FAILED", "FAILED"),
    ),
}


def _write(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True)
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def _results(report: dict[str, Any]) -> dict[str, str]:
    statuses: dict[str, str] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            rule_id = str(node.get("rule_id", ""))
            if ("layers" in rule_id or "cycles" in rule_id) and "status" in node:
                statuses[rule_id.split("/")[0] + "/" + rule_id.split("/")[1]] = str(
                    node["status"]
                )
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(report)
    return statuses


def _run(tmp_path: Path, variant: str, dynamic: bool = True) -> dict[str, Any]:
    reference = _write(tmp_path / "reference", {"__init__.py": _MARKERS, **_SOLUTION})
    changes, _ = _VARIANTS[variant]
    target = _write(tmp_path / variant, {"__init__.py": "", **{**_SOLUTION, **changes}})
    output = tmp_path / "report.json"
    arguments = [
        "--source",
        str(reference),
        "--target",
        str(target),
        "--format",
        "json",
        "--output",
        str(output),
    ]
    main(arguments + (["--dynamic"] if dynamic else []))
    return json.loads(output.read_text(encoding="utf-8"))


@pytest.mark.parametrize("variant", sorted(_VARIANTS))
def test_layers_and_cycles_static_and_at_run_time(tmp_path: Path, variant: str):
    statuses = _results(_run(tmp_path, variant))

    assert (
        statuses["DEP002/enforce_layers"],
        statuses["DEP003/forbid_cycles"],
        statuses["DYN009/enforce_layers"],
        statuses["DYN010/forbid_cycles"],
    ) == _VARIANTS[variant][1]


def test_without_dynamic_only_the_runtime_parts_are_skipped(tmp_path: Path):
    statuses = _results(_run(tmp_path, "upward_import", dynamic=False))

    assert statuses == {
        "DEP002/enforce_layers": "FAILED",
        "DEP003/forbid_cycles": "OK",
        "DYN009/enforce_layers": "SKIPPED",
        "DYN010/forbid_cycles": "SKIPPED",
    }


def test_a_static_violation_names_the_chain_and_the_line(tmp_path: Path):
    report = _run(tmp_path, "lazy_cycle", dynamic=False)
    found: list[dict[str, Any]] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if str(node.get("rule_id", "")).startswith("DEP003"):
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(report)
    (result,) = [item for item in found if "status" in item]
    (cycle,) = result["details"]["cycles"]
    assert cycle["path"] == ["models", "service", "models"]
    assert [step["lineno"] for step in cycle["steps"]] == [7, 2]
