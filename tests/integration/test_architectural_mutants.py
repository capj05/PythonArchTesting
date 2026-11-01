"""The architectural-mutant evaluation in example/architectural_mutants."""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

EXAMPLES = Path(__file__).resolve().parents[2] / "example"
EVALUATION = EXAMPLES / "architectural_mutants"
PROGRAMS = [EVALUATION, EXAMPLES / "architectural_mutants_2"]


@pytest.fixture(name="run")
def fixture_run(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(EVALUATION))
    for name in ("run", "baselines", "baselines.importlinter"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    return importlib.import_module("run")


@pytest.mark.parametrize("program", PROGRAMS, ids=lambda path: path.name)
def test_every_variant_applies_to_the_solution(
    run: ModuleType, program: Path, tmp_path: Path
):
    variants: list[dict[str, Any]] = run._variants(program)
    solution = program / "solution"

    assert len({variant["id"] for variant in variants}) == len(variants)
    for variant in variants:
        target = tmp_path / variant["id"]
        shutil.copytree(solution, target)
        run._apply(variant, target)
        changed = [
            path.name
            for path in sorted(target.glob("*.py"))
            if not (solution / path.name).exists()
            or path.read_text() != (solution / path.name).read_text()
        ]
        removed = [
            path.name
            for path in solution.glob("*.py")
            if not (target / path.name).exists()
        ]
        assert changed or removed, variant["id"]


def test_a_patch_that_does_not_apply_stops_the_run(run: ModuleType, tmp_path: Path):
    shutil.copytree(EVALUATION / "solution", tmp_path / "solution")
    broken = {"id": "X", "patches": [("service.py", "no such text\n", "")]}

    with pytest.raises(SystemExit, match="expected the text once"):
        run._apply(broken, tmp_path / "solution")


def test_the_import_markers_become_import_linter_contracts(run: ModuleType):
    text = run.importlinter.contracts(EVALUATION / "reference", "solution")

    assert "[importlinter:contract:forbid_imports-controller]" in text
    assert "source_modules = solution.service" in text
    assert "    solution.repository" in text
    assert "    pickle" in text
    # mode="direct" on the service's marker, the default on the controller's
    assert text.count("allow_indirect_imports = True") == 1
    # the markers of the whole program, from the root __init__.py
    assert "[importlinter:contract:enforce_layers-root]" in text
    assert "type = layers" in text
    assert "    repository | pricing | events | config" in text
    assert "[importlinter:contract:forbid_cycles-root]" in text
    assert "type = acyclic_siblings" in text


def test_the_solution_passes_and_an_injection_mutant_is_caught_at_run_time(
    run: ModuleType, tmp_path: Path
):
    contracts = tmp_path / ".importlinter"
    contracts.write_text(
        run.importlinter.contracts(EVALUATION / "reference", run.PACKAGE),
        encoding="utf-8",
    )
    variants = {variant["id"]: variant for variant in run._variants(EVALUATION)}
    baseline = run._evaluate(
        {"id": "base", "operator": "-", "description": "-"}, EVALUATION, contracts
    )
    mutant = run._evaluate(variants["M06"], EVALUATION, contracts)

    assert baseline["tools"]["static"]["failing"] == []
    assert baseline["tools"]["runtime"]["failing"] == []
    assert not mutant["tools"]["static"]["caught"]
    assert mutant["tools"]["runtime"]["caught"]
    assert mutant["tools"]["runtime"]["failing"] == ["forbid_runtime_instantiation"]


def test_the_model_mode_needs_no_marker_but_architecture_entry(
    run: ModuleType, tmp_path: Path
):
    contracts = tmp_path / ".importlinter"
    contracts.write_text(
        run.importlinter.contracts(EVALUATION / "reference", run.PACKAGE),
        encoding="utf-8",
    )
    model = run._model_reference(EVALUATION, tmp_path / "model" / "reference")
    variants = {variant["id"]: variant for variant in run._variants(EVALUATION)}
    baseline = run._evaluate(
        {"id": "base", "operator": "-", "description": "-"},
        EVALUATION,
        contracts,
        model,
    )
    mutant = run._evaluate(variants["M05"], EVALUATION, contracts, model)

    assert "architecture_entry" in (model / "__init__.py").read_text(encoding="utf-8")
    assert (model / "controller.py").is_file()
    assert baseline["tools"]["model"]["failing"] == []
    assert mutant["tools"]["model"]["caught"]
    assert mutant["tools"]["model"]["failing"]


def test_variants_can_come_from_another_file(run: ModuleType, tmp_path: Path):
    held_out = tmp_path / "llm_mutants.py"
    held_out.write_text(
        "MUTANTS = [{'id': 'L01', 'operator': 'O1 layer bypass', "
        "'description': 'x', 'patches': [], 'detected_by': []}]\n"
        "EQUIVALENTS = []\n",
        encoding="utf-8",
    )

    assert [v["id"] for v in run._variants(EVALUATION, held_out)] == ["L01"]


def test_a_variant_that_does_not_apply_is_reported_not_fatal(run: ModuleType):
    good = {
        "id": "G",
        "patches": [("service.py", "self._bus = bus\n", "self._bus = bus\n")],
    }
    bad = {"id": "B", "patches": [("service.py", "no such text\n", "")]}

    assert run._apply_error(good, EVALUATION) is None
    assert "expected the text once" in run._apply_error(bad, EVALUATION)


def test_a_failure_without_a_target_is_not_a_catch(run: ModuleType):
    unmatched = {
        "rule_id": "DEP001/forbid_imports/v2",
        "status": "FAILED",
        "details": {"reason": "required_target_missing"},
    }
    model = {
        "rule_id": "DYN011/architecture_entry/v1",
        "status": "FAILED",
        "details": {"reason": "required_target_missing"},
    }

    ours = run._ours([unmatched], {"forbid_imports"})
    assert ours["caught"] is False
    assert ours["unmatched"] == ["forbid_imports"]
    assert run._model([model])["caught"] is False


def test_another_reference_can_be_evaluated(run: ModuleType, tmp_path: Path):
    # A reference with no marker but forbid_imports on the controller.
    reference = tmp_path / "reference"
    shutil.copytree(EVALUATION / "solution", reference)
    controller = reference / "controller.py"
    controller.write_text(
        "from typing import Annotated\n"
        "from pythonarchtesting.rules import forbid_imports\n"
        '__archtest__: Annotated[None, forbid_imports("repository")]\n'
        + controller.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    contracts = tmp_path / ".importlinter"
    contracts.write_text(
        run.importlinter.contracts(reference, run.PACKAGE), encoding="utf-8"
    )
    variants = {variant["id"]: variant for variant in run._variants(EVALUATION)}

    mutant = run._evaluate(
        variants["M02"], EVALUATION, contracts, None, reference=reference
    )

    assert mutant["tools"]["static"]["failing"] == ["forbid_imports"]


def test_a_malformed_patch_is_reported_not_fatal(run: ModuleType):
    malformed = {"id": "B", "patches": [("service.py", "only two")]}

    assert run._apply_error(malformed, EVALUATION)
