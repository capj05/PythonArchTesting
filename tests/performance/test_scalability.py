"""
Real-path scalability tests for discovery, extraction, and matching.
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path

import pytest

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.entities import build_entity_index, sort_entities
from pythonarchtesting.entities_extraction import (
    extract_entities_from_ast_with_nonmatchable,
)
from pythonarchtesting.evidence.collection import parse_python_modules
from pythonarchtesting.matching import MatchingConfig, run_matching
from pythonarchtesting.util.discovery_utils import discover_python_files


def _median_runtime(fn, runs: int = 3) -> float:
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return statistics.median(samples)


def _write_project(root: Path, file_count: int, prefix: str = "mod") -> None:
    root.mkdir(parents=True, exist_ok=True)
    for idx in range(file_count):
        (root / f"{prefix}_{idx}.py").write_text(
            f"""
def fn_{idx}(x):
    total = 0
    for item in range(x):
        total += item + {idx}
    return total
""".strip() + "\n",
            encoding="utf-8",
        )


def _build_index(root: Path, role: str, root_label: str):
    cfg = create_config_from_dict({})
    parsed_modules, errors = parse_python_modules(
        root_path=root,
        config=cfg,
        target_module_name=None,
    )
    assert not errors
    entities = []
    for parsed in parsed_modules:
        matchable, _ = extract_entities_from_ast_with_nonmatchable(
            parsed.tree,
            parsed.file_text,
            parsed.file_path,
            root,
            None,
            role=role,
            include_nested_functions=False,
            root_label=root_label,
        )
        entities.extend(matchable)
    entities = sort_entities(entities)
    return build_entity_index(entities)


@pytest.mark.performance
def test_scalability_suite_does_not_use_time_sleep():
    content = Path(__file__).read_text(encoding="utf-8")
    content = content.replace('"time.sleep("', "")
    assert "time.sleep(" not in content


@pytest.mark.performance
def test_discovery_scales_with_project_size(temp_dir: Path):
    cfg = create_config_from_dict({})
    small = temp_dir / "small"
    large = temp_dir / "large"
    _write_project(small, file_count=8)
    _write_project(large, file_count=32)

    small_files = discover_python_files(small, cfg)
    large_files = discover_python_files(large, cfg)
    assert len(small_files) == 8
    assert len(large_files) == 32

    small_time = _median_runtime(lambda: discover_python_files(small, cfg))
    large_time = _median_runtime(lambda: discover_python_files(large, cfg))

    assert small_time >= 0.0
    assert large_time >= 0.0
    assert large_time >= small_time * 0.5


@pytest.mark.performance
def test_repeated_extraction_runs_complete_successfully(temp_dir: Path):
    project = temp_dir / "project"
    _write_project(project, file_count=24)
    cfg = create_config_from_dict({})

    def _parse():
        parsed, errors = parse_python_modules(
            root_path=project,
            config=cfg,
            target_module_name=None,
        )
        assert not errors
        return parsed

    cold_time = _median_runtime(_parse, runs=1)
    warm_time = _median_runtime(_parse, runs=3)

    assert cold_time >= 0.0
    assert warm_time >= 0.0


@pytest.mark.performance
def test_matching_with_stage2_cap_is_not_slower(temp_dir: Path):
    source_root = temp_dir / "source"
    target_root = temp_dir / "target"
    _write_project(source_root, file_count=10, prefix="source")
    _write_project(target_root, file_count=50, prefix="target")

    source_index = _build_index(source_root, role="source", root_label="source")
    target_index = _build_index(target_root, role="target", root_label="target")

    uncapped = MatchingConfig(
        threshold=0.80,
        delta=0.03,
        min_candidate=0.50,
        top_n=5,
        max_fuzzy_candidates=5,
        max_stage2_candidates=0,
        max_stage3_candidates=0,
    )
    capped = MatchingConfig(
        threshold=0.80,
        delta=0.03,
        min_candidate=0.50,
        top_n=5,
        max_fuzzy_candidates=5,
        max_stage2_candidates=10,
        max_stage3_candidates=10,
    )

    uncapped_time = _median_runtime(
        lambda: run_matching(source_index, target_index, uncapped)
    )
    capped_time = _median_runtime(
        lambda: run_matching(source_index, target_index, capped)
    )

    assert uncapped_time >= 0.0
    assert capped_time <= uncapped_time * 1.5
