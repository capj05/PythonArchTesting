"""``forbid_runtime_calls(..., transitive=True)``: no reaching a layer by a detour.

Without ``transitive`` only the target module's own calls count, so a
controller that reaches the repository through a helper module of its own
passes. With it, every call made while the target runs counts, unless the
chain passes through a module listed in ``through`` — the layer whose job it
is to call on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pythonarchtesting.cli import main
from pythonarchtesting.dynamic.runner import run_cases

_REPOSITORY = """
class OrderRepository:
    def get(self, order_id):
        return {"id": order_id}

    def save(self, order):
        return order
"""

_SERVICE = """
class OrderService:
    def __init__(self, repository):
        self._repository = repository

    def place(self, order_id):
        return self._repository.save({"id": order_id})
"""

_HELPERS = """
from .repository import OrderRepository


def load(order_id):
    return OrderRepository().get(order_id)
"""

_CASES = """[
    {"args": [{"id": "A1"}, {"$new": "service.OrderService",
                             "args": [{"$new": "repository.OrderRepository"}]}]}
]"""

_REFERENCE_CONTROLLER = f"""
from typing import Annotated, Any

from pythonarchtesting.rules import forbid_runtime_calls


def handle(request: Any, service: Any) -> Any:
    __archtest__: Annotated[  # noqa: F842
        None,
        forbid_runtime_calls(
            "repository", transitive=True, through=["service"], cases={_CASES}
        ),
    ]
    return service.place(request["id"])
"""

_TARGETS = {
    "through_service": """
def handle(request, service):
    return service.place(request["id"])
""",
    "direct": """
from .repository import OrderRepository


def handle(request, service):
    return OrderRepository().get(request["id"])
""",
    "via_helper": """
from .helpers import load


def handle(request, service):
    return load(request["id"])
""",
}


def _write(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def _shared() -> dict[str, str]:
    return {
        "repository.py": _REPOSITORY,
        "service.py": _SERVICE,
        "helpers.py": _HELPERS,
    }


def _verdict(tmp_path: Path, target: str, controller: str = _REFERENCE_CONTROLLER):
    reference = _write(
        tmp_path / "reference", {**_shared(), "controller.py": controller}
    )
    solution = _write(
        tmp_path / target, {**_shared(), "controller.py": _TARGETS[target]}
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
    found: list[dict] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if str(node.get("rule_id", "")).startswith("DYN001") and "status" in node:
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(output.read_text(encoding="utf-8")))
    (result,) = found
    return result


@pytest.mark.parametrize(
    ("target", "status"),
    [("through_service", "OK"), ("direct", "FAILED"), ("via_helper", "FAILED")],
)
def test_a_detour_through_another_module_is_caught(
    tmp_path: Path, target: str, status: str
) -> None:
    result = _verdict(tmp_path, target)

    assert result["status"] == status, result["details"].get("summary")


def test_the_violation_names_the_chain_that_reached_the_layer(tmp_path: Path) -> None:
    result = _verdict(tmp_path, "via_helper")

    summary = result["details"]["summary"]
    assert "helpers:load" in summary and "controller:handle" in summary


def test_without_transitive_only_the_modules_own_calls_count(tmp_path: Path) -> None:
    direct_only = _REFERENCE_CONTROLLER.replace(
        'transitive=True, through=["service"], ', ""
    )

    assert _verdict(tmp_path, "via_helper", direct_only)["status"] == "OK"


def test_the_probe_reports_the_chain_of_a_transitive_call(tmp_path: Path) -> None:
    root = _write(
        tmp_path / "pkg", {**_shared(), "controller.py": _TARGETS["via_helper"]}
    )

    outcome = run_cases(
        target_root=root,
        module_path="controller",
        qualname="handle",
        kind="function",
        cases=[{"args": [{"id": "A1"}, None]}],
        init=None,
        timeout_s=10.0,
        observe={"calls": "transitive"},
    )

    calls = outcome.cases[0]["calls"]
    into_repository = [call for call in calls if call["module"] == "repository"]
    assert into_repository, calls
    for call in into_repository:
        assert call["from"] == "helpers"
        assert call["origin"] == {"from": "controller", "caller": "handle"}
        assert call["via"] == [{"module": "helpers", "caller": "load"}]
