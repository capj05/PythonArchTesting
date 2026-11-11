"""The reference's import graph is built once per run, not once per target."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from pythonarchtesting.execution.evaluators import architecture


def test_the_reference_import_graph_is_built_once_per_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Any, ...]] = []

    def built(*args: Any) -> tuple[dict[Any, Any], dict[Any, Any], set[str]]:
        calls.append(args)
        return {}, {}, {"pkg.a"}

    monkeypatch.setattr(architecture, "static_import_edges", built)
    shared: dict[str, Any] = {}
    first = SimpleNamespace(reference_runs=shared, source_by_id={}, source_package="p")
    second = SimpleNamespace(reference_runs=shared, source_by_id={}, source_package="p")

    one = architecture._reference_import_edges(first, True)  # type: ignore[arg-type]
    two = architecture._reference_import_edges(second, True)  # type: ignore[arg-type]
    architecture._reference_import_edges(first, False)  # type: ignore[arg-type]

    assert one is two
    assert len(calls) == 2  # once per ignore_type_checking value
