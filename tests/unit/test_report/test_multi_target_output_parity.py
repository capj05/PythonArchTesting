from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.entities import build_entity_index
from pythonarchtesting.exceptions import ReportGenerationError
from pythonarchtesting.report.api import (
    build_multi_target_report,
    generate_multi_target_report,
)
from pythonarchtesting.state import ValidationResult, ValidationStatus
from pythonarchtesting.state_multi import RunState, TargetRunState


def _golden(name: str) -> str:
    path = Path("tests/fixtures/reports") / name
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()


def _normalize_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\\", "/")
    normalized = re.sub(r"(?<!:)/{2,}", "/", normalized)
    return normalized.strip()


def _normalize_paths(payload):
    if isinstance(payload, dict):
        return {k: _normalize_paths(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [_normalize_paths(item) for item in payload]
    if isinstance(payload, str):
        normalized = payload.replace("\\", "/")
        return re.sub(r"(?<!:)/{2,}", "/", normalized)
    return payload


def _cfg():
    return create_config_from_dict({"report": {}})


def _run_state(cfg) -> RunState:
    empty_index = build_entity_index([])
    return RunState(
        config=cfg,
        source_path=Path("/source"),
        reference_modules=[],
        source_entities=[],
        source_index=empty_index,
        source_by_id={},
        rules=[],
        compiler_results=[],
        compiler_validations=[],
        run_generated_at=datetime(2026, 2, 22, 10, 0, 0, tzinfo=timezone.utc),
        framework_version="test",
    )


def _target(
    target_id: str, path: Path, status: ValidationStatus, rule_id: str
) -> TargetRunState:
    empty_index = build_entity_index([])
    result = ValidationResult(
        status=status,
        description=f"{rule_id} desc",
        check_type=rule_id,
        src_function_name="fn",
        src_package="pkg",
        details={},
        project_name=target_id,
        timestamp=1700000000.0,
    )
    return TargetRunState(
        target_id=target_id,
        target_path=path,
        target_entities=[],
        target_index=empty_index,
        target_by_id={},
        match_results=[],
        match_by_source={},
        rule_results=[],
        validation_results=[result],
    )


def _golden_targets():
    cfg = _cfg()
    run_state = _run_state(cfg)
    targets = [
        _target(
            "b",
            Path("/targets/b"),
            ValidationStatus.FAILED,
            "arch/fail",
        ),
        _target(
            "a",
            Path("/targets/a"),
            ValidationStatus.OK,
            "arch/ok",
        ),
    ]
    return cfg, run_state, targets


def test_multi_target_json_golden():
    cfg, run_state, targets = _golden_targets()
    rendered = generate_multi_target_report(
        run_state, targets, output_format="json", config=cfg
    )
    expected = json.loads(_golden("multi_json.golden"))
    assert _normalize_paths(json.loads(rendered)) == _normalize_paths(expected)


def test_multi_target_markdown_bundle_writes_index_and_target_pages(tmp_path):
    cfg = _cfg()
    run_state = _run_state(cfg)
    targets = [
        _target("B Project", tmp_path / "b", ValidationStatus.FAILED, "arch/fail"),
        _target("A Project", tmp_path / "a", ValidationStatus.OK, "arch/ok"),
    ]

    out = generate_multi_target_report(
        run_state,
        targets,
        output_format="markdown",
        config=cfg,
        output_path=tmp_path / "md",
    )

    root = tmp_path / "md"
    assert out == str(root / "report.md")
    assert (root / "report.md").exists()
    pages = sorted((root / "targets").glob("*.md"))
    assert len(pages) == 2
    index = (root / "report.md").read_text(encoding="utf-8")
    assert "Targets" in index
    assert "targets/a-project.md" in index
    assert "targets/b-project.md" in index


def test_multi_target_markdown_index_golden(tmp_path):
    cfg, run_state, targets = _golden_targets()
    out = generate_multi_target_report(
        run_state,
        targets,
        output_format="markdown",
        config=cfg,
        output_path=tmp_path / "md_golden",
    )

    index = Path(out).read_text(encoding="utf-8")
    assert _normalize_text(index) == _normalize_text(
        _golden("multi_markdown_index.golden")
    )


def test_multi_target_report_rejects_removed_html_format(tmp_path):
    cfg, run_state, targets = _golden_targets()
    with pytest.raises(
        ReportGenerationError,
        match="Unsupported multi-target format 'html'. Available formats: json, markdown",
    ):
        generate_multi_target_report(
            run_state,
            targets,
            output_format="html",
            config=cfg,
            output_path=tmp_path / "html_golden",
        )


def test_target_id_slug_collision_resolution_uses_hash_suffix(tmp_path):
    cfg = _cfg()
    run_state = _run_state(cfg)
    targets = [
        _target("Same Name", tmp_path / "x1", ValidationStatus.OK, "arch/ok"),
        _target("Same_Name", tmp_path / "x2", ValidationStatus.OK, "arch/ok"),
    ]
    report = build_multi_target_report(run_state, targets, cfg)
    ids = [t["target_id"] for t in report["targets"]]
    assert len(ids) == 2
    assert ids[0] != ids[1]
    assert all(
        id_.startswith("same_name") or id_.startswith("same-name") for id_ in ids
    )
