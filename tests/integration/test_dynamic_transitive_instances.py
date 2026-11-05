"""``forbid_runtime_instantiation(..., transitive=True)``: no building through a factory.

Without ``transitive`` an object counts against the code that constructed it,
so a service that has a factory module of its own build its repository
passes. With it, every instance built while the target runs counts, unless
it was built by code of a module listed in ``through``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pythonarchtesting.cli import main
from pythonarchtesting.dynamic.runner import run_cases

_REPOSITORY = """
class Row:
    pass


class OrderRepository:
    def save(self, order):
        Row()
        return order
"""

_FACTORY = """
from .repository import OrderRepository


def make_repository():
    return OrderRepository()
"""


def _service(extra: str) -> str:
    return f"""
from typing import Annotated, Any

from pythonarchtesting.rules import forbid_runtime_instantiation


class OrderService:
    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def place(self, order_id: Any) -> Any:
        __archtest__: Annotated[  # noqa: F842
            None,
            forbid_runtime_instantiation(
                "repository", {extra}init={{"args": [{{"$new": "repository.OrderRepository"}}]}},
                cases=[{{"args": ["A1"]}}],
            ),
        ]
        return self.repository.save({{"id": order_id}})
"""


_TARGETS = {
    "injected": """
class OrderService:
    def __init__(self, repository):
        self.repository = repository

    def place(self, order_id):
        return self.repository.save({"id": order_id})
""",
    "factory": """
from .factory import make_repository


class OrderService:
    def __init__(self, repository):
        self.repository = repository

    def place(self, order_id):
        return make_repository().save({"id": order_id})
""",
}


def _write(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def _result(tmp_path: Path, target: str, extra: str) -> dict:
    shared = {"repository.py": _REPOSITORY, "factory.py": _FACTORY}
    reference = _write(
        tmp_path / "reference", {**shared, "service.py": _service(extra)}
    )
    solution = _write(tmp_path / target, {**shared, "service.py": _TARGETS[target]})
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
            if str(node.get("rule_id", "")).startswith("DYN004") and "status" in node:
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(output.read_text(encoding="utf-8")))
    (result,) = found
    return result


_TRANSITIVE = 'transitive=True, through=["repository"], '


@pytest.mark.parametrize(
    ("target", "extra", "status"),
    [
        ("factory", "", "OK"),
        ("factory", _TRANSITIVE, "FAILED"),
        ("injected", _TRANSITIVE, "OK"),
    ],
)
def test_building_through_a_factory_module_is_caught_with_transitive(
    tmp_path: Path, target: str, extra: str, status: str
) -> None:
    result = _result(tmp_path, target, extra)

    assert result["status"] == status, result["details"].get("summary")


def test_the_violation_names_the_factory(tmp_path: Path) -> None:
    summary = _result(tmp_path, "factory", _TRANSITIVE)["details"]["summary"]

    assert "factory:make_repository" in summary
    assert "service:OrderService.place" in summary


def test_the_probe_reports_the_chain_of_a_transitive_instance(tmp_path: Path) -> None:
    root = _write(
        tmp_path / "pkg",
        {
            "repository.py": _REPOSITORY,
            "factory.py": _FACTORY,
            "service.py": _TARGETS["factory"],
        },
    )

    outcome = run_cases(
        target_root=root,
        module_path="service",
        qualname="OrderService.place",
        kind="method",
        cases=[{"args": ["A1"]}],
        init={"args": [None]},
        timeout_s=10.0,
        observe={"instances": "transitive"},
    )

    by_class = {item["class"]: item for item in outcome.cases[0]["instances"]}
    assert by_class["OrderRepository"]["origin"] == {
        "from": "service",
        "caller": "OrderService.place",
        "line": 10,
    }
    assert by_class["OrderRepository"]["via"] == [
        {"module": "factory", "caller": "make_repository"}
    ]
    assert by_class["Row"]["via"] == [
        {"module": "repository", "caller": "OrderRepository.save"}
    ]
