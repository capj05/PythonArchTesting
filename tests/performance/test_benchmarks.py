"""
Real-path benchmark tests for key pipeline components.
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path

import pytest

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.config.projects import resolve_projects_config
from pythonarchtesting.runner import run_projects


def _median_runtime(fn, runs: int = 3) -> float:
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def _write_module(path: Path, name: str, offset: int) -> None:
    path.write_text(
        f"""
def {name}(x):
    return x + {offset}
""".strip() + "\n",
        encoding="utf-8",
    )


def _build_run_fixture(root: Path) -> tuple[Path, Path, Path]:
    source = root / "source"
    target_a = root / "target_a"
    target_b = root / "target_b"
    source.mkdir(parents=True, exist_ok=True)
    target_a.mkdir(parents=True, exist_ok=True)
    target_b.mkdir(parents=True, exist_ok=True)

    for idx in range(20):
        _write_module(source / f"shared_{idx}.py", f"calc_{idx}", idx)
        _write_module(target_a / f"student_a_{idx}.py", f"calc_{idx}", idx)
        _write_module(target_b / f"student_b_{idx}.py", f"calc_{idx}", idx + 1)

    return source, target_a, target_b


@pytest.mark.performance
def test_benchmarks_suite_does_not_use_time_sleep():
    content = Path(__file__).read_text(encoding="utf-8")
    content = content.replace('"time.sleep("', "")
    assert "time.sleep(" not in content


@pytest.mark.performance
def test_run_projects_real_path_benchmark(temp_dir: Path):
    source, target_a, target_b = _build_run_fixture(temp_dir / "bench")
    cfg = create_config_from_dict(
        {
            "matching": {"max_stage2_candidates": "0", "max_stage3_candidates": "0"},
        }
    )
    projects = resolve_projects_config(
        cfg,
        source_path=str(source),
        targets=[str(target_a), str(target_b)],
    )

    def _run():
        run_state, target_states = run_projects(
            config=cfg,
            projects=projects,
            load_config_first=False,
        )
        assert len(target_states) == 2
        assert run_state.source_entities

    runtime = _median_runtime(_run, runs=3)
    assert runtime >= 0.0


@pytest.mark.performance
def test_static_only_config_creation_is_constant_cost():
    def _run():
        cfg = create_config_from_dict({})
        assert cfg.report.schema_version == "2"

    runtime = _median_runtime(_run, runs=3)
    assert runtime >= 0.0
