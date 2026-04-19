from __future__ import annotations

import textwrap
from pathlib import Path

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.matching import MatchStatus
from pythonarchtesting.runner import run_projects


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def test_run_projects_matches_stub_reference_project_against_python_target(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "reference"
    target_dir = tmp_path / "target"

    _write_file(
        source_dir / "calculator.pyi",
        """
        from typing import Annotated

        def add(
            a: int,
            b: int,
        ) -> Annotated[int, ("required_entity_signature", {"mode": "exact"})]: ...
        """,
    )
    _write_file(
        target_dir / "calculator.py",
        """
        def add(a: int, b: int) -> int:
            return a + b
        """,
    )
    # Use default *.py for target discovery; source uses reference_modules with stub file
    config = create_config_from_dict(
        {
            "projects": {"source_path": str(source_dir)},
        }
    )

    run_state, target_states = run_projects(
        config=config,
        targets=[str(target_dir)],
        source_path=str(source_dir),
        reference_modules=["calculator"],
        load_config_first=False,
    )
    target_state = target_states[0]

    assert any(
        entity.module_path == "calculator" for entity in run_state.source_entities
    )
    assert any(
        entity.module_path == "calculator" for entity in target_state.target_entities
    )
    assert any(
        match.status == MatchStatus.MATCHED for match in target_state.match_results
    )
