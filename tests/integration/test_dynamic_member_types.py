"""``require_runtime_members(..., types=...)``: what an injected member is.

A service that must keep its repository in ``self.repository`` can satisfy
the name with anything. ``types`` asks what the built instance actually
holds — the reference's class, or a subclass of it, under whatever name the
target gave it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pythonarchtesting.cli import main

_REPOSITORY = """
class OrderRepository:
    pass


class CachedRepository(OrderRepository):
    pass
"""

_REFERENCE_SERVICE = """
from typing import Annotated, Any

from pythonarchtesting.rules import require_runtime_members


class OrderService:
    __archtest__: Annotated[  # noqa: F842
        None,
        require_runtime_members(
            "repository",
            types={"repository": "repository.OrderRepository"},
            cases=[{"args": [{"$new": "repository.OrderRepository"}]}],
        ),
    ]

    def __init__(self, repository: Any) -> None:
        self.repository = repository
"""

_TARGETS = {
    "keeps_it": (
        "class OrderService:\n    def __init__(self, repository):\n"
        "        self.repository = repository\n"
    ),
    "keeps_a_subclass": (
        "from .repository import CachedRepository\n\n\n"
        "class OrderService:\n    def __init__(self, repository):\n"
        "        self.repository = CachedRepository()\n"
    ),
    "keeps_a_dict": (
        "class OrderService:\n    def __init__(self, repository):\n"
        "        self.repository = {}\n"
    ),
}


def _write(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def _result(tmp_path: Path, target: str, storage: str = "repository") -> dict:
    reference = _write(
        tmp_path / "reference",
        {"repository.py": _REPOSITORY, "service.py": _REFERENCE_SERVICE},
    )
    service = _TARGETS[target].replace(".repository import", f".{storage} import")
    solution = _write(
        tmp_path / target, {f"{storage}.py": _REPOSITORY, "service.py": service}
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
            if str(node.get("rule_id", "")).startswith("DYN005") and "status" in node:
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
    [("keeps_it", "OK"), ("keeps_a_subclass", "OK"), ("keeps_a_dict", "FAILED")],
)
def test_the_member_must_hold_an_instance_of_the_class(
    tmp_path: Path, target: str, status: str
) -> None:
    result = _result(tmp_path, target)

    assert result["status"] == status, result["details"].get("summary")


def test_the_violation_names_what_the_member_holds(tmp_path: Path) -> None:
    summary = _result(tmp_path, "keeps_a_dict")["details"]["summary"]

    assert "'repository' is a dict" in summary
    assert "OrderRepository" in summary


def test_the_class_is_found_in_a_renamed_module(tmp_path: Path) -> None:
    assert _result(tmp_path, "keeps_it", storage="storage")["status"] == "OK"
