"""The reference runs once per rule in a run, not once per target.

``enforce_reference_calls`` and runtime ``enforce_flow`` compare each target
with what the reference did on the same cases. The reference does the same
thing for every target, so a class of submissions must not pay for running it
again for each one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.cli import main
from pythonarchtesting.dynamic import runner

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHOWCASE = _REPO_ROOT / "example" / "rule_showcase"


@pytest.fixture(autouse=True)
def _repo_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(_REPO_ROOT)


@pytest.mark.parametrize("family", ["dyn001_reference_calls", "flw002_runtime_flow"])
def test_every_target_reuses_one_run_of_the_reference(
    family: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference = (_SHOWCASE / family / "reference").resolve()
    assignments = _SHOWCASE / family / "assignments"
    roots: list[Path] = []
    original = runner._run_probe

    def counting(request: dict[str, Any], *, target_root: Path, **kwargs: Any):
        roots.append(Path(target_root).resolve())
        return original(request, target_root=target_root, **kwargs)

    monkeypatch.setattr(runner, "_run_probe", counting)
    main(
        [
            "--source",
            str(reference),
            "--targets-dir",
            str(assignments),
            "--format",
            "json",
            "--output",
            str(tmp_path / "report.json"),
            "--dynamic",
        ]
    )

    targets = [path for path in assignments.iterdir() if path.is_dir()]
    reference_runs = sum(1 for root in roots if root == reference)
    assert len(targets) > 1
    assert len(roots) - reference_runs >= len(targets)
    assert reference_runs == 1
