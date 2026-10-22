"""``enforce_reference_calls(..., allow_new_modules=True)``: helpers of one's own.

The reference's module graph is exact: a target that moves part of the
controller into a new ``helpers`` module adds the edge ``controller ->
helpers`` and fails, although its layering is the reference's. With
``allow_new_modules`` a module the reference does not have counts as part of
the modules that call it, so its calls must still be ones they may make.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pythonarchtesting.cli import main
from pythonarchtesting.execution.evaluators.runtime_structure import _fold_new_modules

_REPOSITORY = """
class OrderRepository:
    def save(self, order):
        return order
"""

_SERVICE = """
class OrderService:
    def __init__(self, repository):
        self.repository = repository

    def place(self, order_id):
        return self.repository.save({"id": order_id})
"""


def _controller(extra: str) -> str:
    return f"""
from typing import Annotated, Any

from pythonarchtesting.rules import enforce_reference_calls


def handle(request: Any, service: Any) -> Any:
    __archtest__: Annotated[  # noqa: F842
        None,
        enforce_reference_calls(
            {extra}cases=[{{"args": [{{"id": "A1"}}, {{"$new": "service.OrderService",
                "args": [{{"$new": "repository.OrderRepository"}}]}}]}}]
        ),
    ]
    return service.place(request["id"])
"""


_TARGETS = {
    "helper_calls_service": (
        "from .helpers import place\n\n\ndef handle(request, service):\n"
        '    return place(service, request["id"])\n',
        "def place(service, order_id):\n    return service.place(order_id)\n",
    ),
    "helper_bypasses_service": (
        "from .helpers import place\n\n\ndef handle(request, service):\n"
        '    return place(service, request["id"])\n',
        "def place(service, order_id):\n"
        "    return service.repository.save({'id': order_id})\n",
    ),
}


def _write(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def _status(tmp_path: Path, target: str, extra: str) -> str:
    shared = {"repository.py": _REPOSITORY, "service.py": _SERVICE}
    reference = _write(
        tmp_path / "reference", {**shared, "controller.py": _controller(extra)}
    )
    controller, helpers = _TARGETS[target]
    solution = _write(
        tmp_path / target,
        {**shared, "controller.py": controller, "helpers.py": helpers},
    )
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(reference),
            "--target",
            str(solution),
            "--format",
            "json",
            "--output",
            str(output),
            "--dynamic",
        ]
    )
    statuses: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if str(node.get("rule_id", "")).startswith("DYN001") and "status" in node:
                statuses.append(str(node["status"]))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(output.read_text(encoding="utf-8")))
    (status,) = statuses
    return status


@pytest.mark.parametrize(
    ("target", "extra", "status"),
    [
        ("helper_calls_service", "", "FAILED"),
        ("helper_calls_service", "allow_new_modules=True, ", "OK"),
        ("helper_bypasses_service", "allow_new_modules=True, ", "FAILED"),
    ],
)
def test_a_new_module_counts_as_part_of_its_callers(
    tmp_path: Path, target: str, extra: str, status: str
) -> None:
    assert _status(tmp_path, target, extra) == status


def test_folding_follows_chains_of_new_modules() -> None:
    edges = {
        ("controller", "helpers"): {},
        ("helpers", "formatting"): {},
        ("formatting", "service"): {},
        ("service", "repository"): {},
    }

    folded = _fold_new_modules(edges, {"controller", "service", "repository"})

    assert set(folded) == {("controller", "service"), ("service", "repository")}
