"""The architectural-mutant evaluation in example/architectural_mutants."""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

EVALUATION = Path(__file__).resolve().parents[2] / "example" / "architectural_mutants"


@pytest.fixture(name="run")
def fixture_run(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(EVALUATION))
    for name in ("run", "mutants"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    return importlib.import_module("run")


def _variants(run: ModuleType) -> list[dict[str, Any]]:
    return list(run.MUTANTS) + list(run.EQUIVALENTS)


def test_every_variant_applies_to_the_solution(run: ModuleType, tmp_path: Path):
    variants = _variants(run)

    assert len({variant["id"] for variant in variants}) == len(variants)
    for variant in variants:
        target = tmp_path / variant["id"]
        shutil.copytree(run.SOLUTION, target)
        run._apply(variant, target)
        changed = [
            path.name
            for path in sorted(target.glob("*.py"))
            if not (run.SOLUTION / path.name).exists()
            or path.read_text() != (run.SOLUTION / path.name).read_text()
        ]
        assert changed, variant["id"]


def test_a_patch_that_does_not_apply_stops_the_run(run: ModuleType, tmp_path: Path):
    shutil.copytree(run.SOLUTION, tmp_path / "solution")
    broken = {"id": "X", "patches": [("service.py", "no such text\n", "")]}

    with pytest.raises(SystemExit, match="expected the text once"):
        run._apply(broken, tmp_path / "solution")


def test_the_solution_passes_and_an_injection_mutant_is_caught_at_run_time(
    run: ModuleType,
):
    baseline = run._evaluate({"id": "base", "operator": "-", "description": "-"})
    mutant = run._evaluate(
        next(variant for variant in run.MUTANTS if variant["id"] == "M06")
    )

    assert (baseline["static"], baseline["runtime"]) == ([], [])
    assert not mutant["static_caught"]
    assert mutant["runtime_caught"]
    assert mutant["runtime"] == ["forbid_runtime_instantiation"]
