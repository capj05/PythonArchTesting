from __future__ import annotations

import textwrap
from pathlib import Path

from src.config.data import create_config_from_dict
from src.matching import MatchStatus
from src.state import ProjectState


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def test_project_state_matches_stub_reference_project_against_python_target(
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
    config = create_config_from_dict(
        {
            "discovery": {"included_file_patterns": ["*.pyi"]},
            "projects": {"source_path": str(source_dir)},
        }
    )
    state = ProjectState(str(target_dir), ["calculator"], config=config)

    state.initialize(str(target_dir))
    state.reference_modules = ["calculator"]
    state.build_entity_indexes()
    state.run_matching()

    assert any(entity.module_path == "calculator" for entity in state.source_entities)
    assert any(entity.module_path == "calculator" for entity in state.target_entities)
    assert any(match.status == MatchStatus.MATCHED for match in state.match_results)
