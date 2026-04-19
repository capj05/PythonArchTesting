from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from pythonarchtesting.cli import main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fixture_source_targets() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[1] / "fixtures" / "e2e" / "project_1"
    return (
        root / "reference",
        root / "assignments",
    )


def _real_example_source_targets() -> tuple[Path, Path]:
    root = _repo_root() / "example" / "project_1"
    return (
        root / "reference",
        root / "assignments",
    )


def _write_static_only_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "annotation_e2e.conf"
    config_path.write_text(
        (
            "[report]\n"
            "include_config_snapshot = false\n"
            "validate_schema_v2 = true\n"
        ),
        encoding="utf-8",
    )
    return config_path


def _run_cli(argv: list[str]) -> tuple[int, str]:
    stream = io.StringIO()
    with redirect_stdout(stream):
        exit_code = main(argv)
    return exit_code, stream.getvalue()


def _write_annotation_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "source"
    target = base / "target"
    source.mkdir()
    target.mkdir()

    (source / "reference.py").write_text(
        (
            "from typing import Annotated\n"
            "from pythonarchtesting.rules import required_entity_signature\n"
            "\n"
            "def normalize(value: str) -> str:\n"
            '    __archtest__: Annotated[None, required_entity_signature(mode="exact")]\n'
            "    return value.strip()\n"
        ),
        encoding="utf-8",
    )
    (target / "reference.py").write_text(
        ("def normalize(value: str) -> str:\n" "    return value.strip()\n"),
        encoding="utf-8",
    )
    return source, target


def _write_signature_annotation_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "signature_source"
    target = base / "signature_target"
    source.mkdir()
    target.mkdir()

    (source / "reference.py").write_text(
        (
            "from typing import Annotated\n"
            "from pythonarchtesting.rules import required_entity_signature\n"
            "\n"
            "def normalize(\n"
            '    value: Annotated[str, required_entity_signature(mode="exact")],\n'
            ') -> Annotated[str, required_entity_signature(mode="exact")]:\n'
            "    return value.strip()\n"
        ),
        encoding="utf-8",
    )
    (target / "reference.py").write_text(
        ("def normalize(value: str) -> str:\n" "    return value.strip()\n"),
        encoding="utf-8",
    )
    return source, target


def _write_protocol_annotation_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "protocol_source"
    target = base / "protocol_target"
    source.mkdir()
    target.mkdir()

    (source / "reference.py").write_text(
        (
            "from typing import Annotated, Protocol\n"
            "from pythonarchtesting.rules import implements_protocol\n"
            "\n"
            "class Repository(Protocol):\n"
            "    def get(self, item_id: str) -> str:\n"
            "        ...\n"
            "\n"
            "class SqlRepository:\n"
            '    __archtest__: Annotated[None, implements_protocol("reference.Repository")]\n'
        ),
        encoding="utf-8",
    )
    (target / "reference.py").write_text(
        (
            "class SqlRepository:\n"
            "    def get(self, item_id: str) -> str:\n"
            "        return item_id\n"
        ),
        encoding="utf-8",
    )
    return source, target


def _write_protocol_signature_annotation_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "protocol_signature_source"
    target = base / "protocol_signature_target"
    source.mkdir()
    target.mkdir()

    (source / "reference.py").write_text(
        (
            "from typing import Annotated, Protocol\n"
            "from pythonarchtesting.rules import implements_protocol\n"
            "\n"
            "class Repository(Protocol):\n"
            "    def get(self, item_id: str) -> str:\n"
            "        ...\n"
            "\n"
            "def process(\n"
            "    repo: Annotated[object, implements_protocol(Repository)],\n"
            ") -> Annotated[object, implements_protocol(Repository)]:\n"
            "    return repo\n"
        ),
        encoding="utf-8",
    )
    (target / "reference.py").write_text(
        (
            "class SqlRepository:\n"
            "    def get(self, item_id: str) -> str:\n"
            "        return item_id\n"
            "\n"
            "def process(repo: SqlRepository) -> SqlRepository:\n"
            "    return repo\n"
        ),
        encoding="utf-8",
    )
    return source, target


def test_example_annotation_rules_e2e_json_contains_only_supported_rule_families(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, targets_dir = _fixture_source_targets()
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "report.json"

    exit_code, _ = _run_cli(
        [
            "--config",
            str(config_path),
            "--source",
            str(source),
            "--targets-dir",
            str(targets_dir),
            "--format",
            "json",
            "--output",
            str(json_out),
        ]
    )

    assert exit_code == 1
    report = json.loads(json_out.read_text(encoding="utf-8"))

    supported_rule_ids = {
        "API001/required_entity_signature/v1",
        "API001/required_entity_signature_return/v1",
        "API002/required_method/v1",
        "DEP001/forbid_imports/v2",
        "PRO001/implements_protocol/v1",
        "PRO002/implements_protocol_signature/v1",
    }
    statuses = set()

    for target in report.get("targets") or []:
        for item in target.get("results") or []:
            rule_id = str(item.get("rule_id") or "")
            statuses.add(str(item.get("status") or ""))
            assert rule_id in supported_rule_ids
            assert not rule_id.startswith(("arch/", "structural/"))
            assert "list_comprehension" not in rule_id

    assert "OK" in statuses
    assert "FAILED" in statuses


def test_annotation_fixture_emits_only_supported_results(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_annotation_fixture(tmp_path)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "annotation_report.json"

    exit_code, _ = _run_cli(
        [
            "--config",
            str(config_path),
            "--source",
            str(source),
            "--target",
            str(target),
            "--format",
            "json",
            "--output",
            str(json_out),
        ]
    )

    assert exit_code == 0

    report = json.loads(json_out.read_text(encoding="utf-8"))
    results = [
        item
        for target_report in report.get("targets") or []
        for item in target_report.get("results") or []
    ]

    assert [item.get("rule_id") for item in results] == [
        "API001/required_entity_signature/v1",
        "API001/required_entity_signature_return/v1",
    ]


def test_signature_annotation_fixture_emits_required_signature_results(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_signature_annotation_fixture(tmp_path)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "signature_annotation_report.json"

    exit_code, _ = _run_cli(
        [
            "--config",
            str(config_path),
            "--source",
            str(source),
            "--target",
            str(target),
            "--format",
            "json",
            "--output",
            str(json_out),
        ]
    )

    assert exit_code == 0

    report = json.loads(json_out.read_text(encoding="utf-8"))
    results = [
        item
        for target_report in report.get("targets") or []
        for item in target_report.get("results") or []
    ]

    assert [item.get("rule_id") for item in results] == [
        "API001/required_entity_signature/v1/d0",
        "API001/required_entity_signature/v1/d1",
        "API001/required_entity_signature_return/v1/d0",
        "API001/required_entity_signature_return/v1/d1",
    ]


def test_protocol_annotation_fixture_emits_protocol_results(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_protocol_annotation_fixture(tmp_path)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "protocol_annotation_report.json"

    exit_code, _ = _run_cli(
        [
            "--config",
            str(config_path),
            "--source",
            str(source),
            "--target",
            str(target),
            "--format",
            "json",
            "--output",
            str(json_out),
        ]
    )

    assert exit_code == 0

    report = json.loads(json_out.read_text(encoding="utf-8"))
    results = [
        item
        for target_report in report.get("targets") or []
        for item in target_report.get("results") or []
    ]

    assert [item.get("rule_id") for item in results] == [
        "PRO001/implements_protocol/v1",
    ]


def test_protocol_signature_annotation_fixture_emits_protocol_signature_results(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_protocol_signature_annotation_fixture(tmp_path)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "protocol_signature_annotation_report.json"

    exit_code, _ = _run_cli(
        [
            "--config",
            str(config_path),
            "--source",
            str(source),
            "--target",
            str(target),
            "--format",
            "json",
            "--output",
            str(json_out),
        ]
    )

    assert exit_code == 0

    report = json.loads(json_out.read_text(encoding="utf-8"))
    results = [
        item
        for target_report in report.get("targets") or []
        for item in target_report.get("results") or []
    ]

    assert [item.get("rule_id") for item in results] == [
        "PRO002/implements_protocol_signature/v1/d0",
        "PRO002/implements_protocol_signature/v1/d1",
    ]


def test_real_example_reference_passes_declaration_validation(monkeypatch) -> None:
    monkeypatch.chdir(_repo_root())
    source, _ = _real_example_source_targets()

    exit_code, output = _run_cli(
        [
            "--validate-declarations",
            "--source",
            str(source),
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(output)
    assert payload["summary"]["invalid_declarations"] == 0
    assert payload["summary"]["errors_total"] == 0
    assert payload["diagnostics"] == []


def test_real_example_run_report_json_is_accurate(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(_repo_root())
    source, targets_dir = _real_example_source_targets()
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "real_example_report.json"

    exit_code, _ = _run_cli(
        [
            "--config",
            str(config_path),
            "--source",
            str(source),
            "--targets-dir",
            str(targets_dir),
            "--format",
            "json",
            "--output",
            str(json_out),
        ]
    )

    assert exit_code == 1

    report = json.loads(json_out.read_text(encoding="utf-8"))
    targets = {target["display_name"]: target for target in report.get("targets") or []}

    assert set(targets) == {"target1", "target2", "target3", "target4", "target5"}
    assert report["summary"]["targets_total"] == 5
    assert report["summary"]["targets_passed"] == 1
    assert report["summary"]["targets_failed"] == 4

    for target in targets.values():
        assert all(
            item.get("rule_id") != "compiler_invalid_declaration"
            for item in target.get("results") or []
        )

    target1 = targets["target1"]
    assert target1["exit_code"] == 0
    assert target1["summary"]["status_counts"] == {"OK": 5}

    target2 = targets["target2"]
    assert target2["exit_code"] == 1
    assert any(
        item["rule_id"] == "API002/required_method/v1"
        and item["status"] == "FAILED"
        and "parameter annotation mismatch" in item["message"]
        for item in target2["results"]
    )

    target3 = targets["target3"]
    assert target3["exit_code"] == 1
    assert any(
        item["rule_id"] == "DEP001/forbid_imports/v2"
        and item["status"] == "FAILED"
        and "statistics" in item["message"]
        for item in target3["results"]
    )
    assert any(
        item["rule_id"] == "API001/required_entity_signature_return/v1"
        and item["status"] == "FAILED"
        and "return annotation mismatch" in item["message"]
        for item in target3["results"]
    )

    for name in ("target4", "target5"):
        assert any(
            item["rule_id"] == "DEP001/forbid_imports/v2" and item["status"] == "OK"
            for item in targets[name]["results"]
        )
        assert any(
            item["rule_id"] == "API001/required_entity_signature/v1"
            and item["status"] == "FAILED"
            and item["details"]["match_status"] == "unmatched"
            for item in targets[name]["results"]
        )
        assert any(
            item["rule_id"] == "API002/required_method/v1"
            and item["status"] == "FAILED"
            and item["details"].get("match_status") in {"low_confidence", "unmatched"}
            for item in targets[name]["results"]
        )
        assert any(
            item["rule_id"] == "API001/required_entity_signature_return/v1"
            and item["status"] == "SKIPPED"
            for item in targets[name]["results"]
        )


def test_real_example_markdown_bundle_is_written(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(_repo_root())
    source, targets_dir = _real_example_source_targets()
    config_path = _write_static_only_config(tmp_path)
    markdown_out = tmp_path / "real_example_markdown"

    exit_code, _ = _run_cli(
        [
            "--config",
            str(config_path),
            "--source",
            str(source),
            "--targets-dir",
            str(targets_dir),
            "--format",
            "markdown",
            "--output",
            str(markdown_out),
        ]
    )

    assert exit_code == 1
    assert (markdown_out / "report.md").is_file()
    for target_name in ("target1", "target2", "target3", "target4", "target5"):
        assert (markdown_out / "targets" / f"{target_name}.md").is_file()
