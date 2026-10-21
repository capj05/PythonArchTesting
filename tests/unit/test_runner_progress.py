from __future__ import annotations

import shutil
from pathlib import Path

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.runner import run_projects

EXAMPLE = Path(__file__).parents[2] / "example" / "architectural_mutants"


def test_run_projects_reports_each_target(tmp_path: Path) -> None:
    solution = EXAMPLE / "solution"
    solution_copy = tmp_path / "solution_copy"
    shutil.copytree(solution, solution_copy)
    calls: list[tuple[int, int, str]] = []

    _, target_states = run_projects(
        config=create_config_from_dict({}),
        source_path=str(EXAMPLE / "reference"),
        targets=[str(solution), str(solution_copy)],
        load_config_first=False,
        on_target_done=lambda index, total, target_id: calls.append(
            (index, total, target_id)
        ),
    )

    ids = [state.target_id for state in target_states]
    assert calls == [(1, 2, ids[0]), (2, 2, ids[1])]
