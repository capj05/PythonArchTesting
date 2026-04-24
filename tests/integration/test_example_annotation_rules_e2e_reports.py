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


def _write_flexible_method_annotation_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "flexible_method_source"
    target = base / "flexible_method_target"
    source.mkdir()
    target.mkdir()

    (source / "reference.py").write_text(
        (
            "from typing import Annotated\n"
            "from pythonarchtesting.rules import required_method\n"
            "\n"
            "class AliasProcessor:\n"
            "    def run(self, data: int) -> int:\n"
            "        __archtest__: Annotated[\n"
            "            None,\n"
            '            required_method(name_match="alias", aliases=["execute"]),\n'
            "        ]\n"
            "        return data\n"
            "\n"
            "class RegexProcessor:\n"
            "    def run(self, data: int) -> int:\n"
            "        __archtest__: Annotated[\n"
            "            None,\n"
            '            required_method(name_match="regex", pattern="fetch_[a-z]+"),\n'
            "        ]\n"
            "        return data\n"
            "\n"
            "class AnyProcessor:\n"
            "    def run(self, data: int) -> int:\n"
            '        __archtest__: Annotated[None, required_method(name_match="any")]\n'
            "        return data\n"
        ),
        encoding="utf-8",
    )
    (target / "reference.py").write_text(
        (
            "class AliasProcessor:\n"
            "    def execute(self, data: int) -> int:\n"
            "        return data\n"
            "\n"
            "class RegexProcessor:\n"
            "    def fetch_data(self, data: int) -> int:\n"
            "        return data\n"
            "\n"
            "    def fetch_value(self, data: int) -> int:\n"
            "        return data\n"
            "\n"
            "class AnyProcessor:\n"
            "    def process(self, data: int) -> int:\n"
            "        return data\n"
        ),
        encoding="utf-8",
    )
    return source, target


def _write_optional_method_annotation_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "optional_method_source"
    target = base / "optional_method_target"
    source.mkdir()
    target.mkdir()

    (source / "reference.py").write_text(
        (
            "from typing import Annotated\n"
            "from pythonarchtesting.rules import required_method\n"
            "\n"
            "class PresentProcessor:\n"
            "    def run(self, data: int) -> int:\n"
            "        __archtest__: Annotated[\n"
            "            None,\n"
            '            required_method(signature_mode="compatible", allow_missing=True),\n'
            "        ]\n"
            "        return data\n"
            "\n"
            "class AbsentProcessor:\n"
            "    def run(self, data: int) -> int:\n"
            "        __archtest__: Annotated[\n"
            "            None,\n"
            '            required_method(signature_mode="compatible", allow_missing=True),\n'
            "        ]\n"
            "        return data\n"
            "\n"
            "class InvalidProcessor:\n"
            "    def run(self, data: int) -> int:\n"
            "        __archtest__: Annotated[\n"
            "            None,\n"
            '            required_method(signature_mode="compatible", allow_missing=True),\n'
            "        ]\n"
            "        return data\n"
        ),
        encoding="utf-8",
    )
    (target / "reference.py").write_text(
        (
            "class PresentProcessor:\n"
            "    def run(self, data: int) -> int:\n"
            "        return data\n"
            "\n"
            "class AbsentProcessor:\n"
            "    pass\n"
            "\n"
            "class InvalidProcessor:\n"
            "    def run(self, data: str) -> int:\n"
            "        return 0\n"
        ),
        encoding="utf-8",
    )
    return source, target


def _write_any_params_method_annotation_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "any_params_method_source"
    target = base / "any_params_method_target"
    source.mkdir()
    target.mkdir()

    (source / "reference.py").write_text(
        (
            "from typing import Annotated\n"
            "from pythonarchtesting.rules import required_method\n"
            "\n"
            "class AnyParamsProcessor:\n"
            "    def run(self, data: int) -> int:\n"
            "        __archtest__: Annotated[\n"
            "            None,\n"
            '            required_method(signature_mode="any"),\n'
            "        ]\n"
            "        return data\n"
            "\n"
            "class AnyParamsKindMismatchProcessor:\n"
            "    @classmethod\n"
            "    def build(cls, data: int) -> int:\n"
            "        __archtest__: Annotated[\n"
            "            None,\n"
            '            required_method(signature_mode="any"),\n'
            "        ]\n"
            "        return data\n"
        ),
        encoding="utf-8",
    )
    (target / "reference.py").write_text(
        (
            "class AnyParamsProcessor:\n"
            "    def run(self, payload: str, enabled: bool, *, timeout: float) -> int:\n"
            "        return 1\n"
            "\n"
            "class AnyParamsKindMismatchProcessor:\n"
            "    def build(self, payload: str, enabled: bool) -> int:\n"
            "        return 1\n"
        ),
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


def _write_subclass_annotation_fixture(
    base: Path,
    *,
    inheriting: bool,
) -> tuple[Path, Path]:
    source = base / "subclass_source"
    target = base / "subclass_target"
    source.mkdir()
    target.mkdir()

    (source / "reference.py").write_text(
        (
            "from typing import Annotated\n"
            "from pythonarchtesting.rules import subclass_of\n"
            "\n"
            "class BaseRepository:\n"
            "    pass\n"
            "\n"
            "class CsvRepository(BaseRepository):\n"
            '    __archtest__: Annotated[None, subclass_of("reference.BaseRepository")]\n'
        ),
        encoding="utf-8",
    )
    base_clause = "(BaseRepository)" if inheriting else ""
    (target / "reference.py").write_text(
        (
            "class BaseRepository:\n"
            "    pass\n"
            "\n"
            f"class CsvRepository{base_clause}:\n"
            "    pass\n"
        ),
        encoding="utf-8",
    )
    return source, target


def _write_attribute_annotation_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "attribute_source"
    target = base / "attribute_target"
    source.mkdir()
    target.mkdir()

    (source / "reference.py").write_text(
        (
            "from typing import Annotated\n"
            "from pythonarchtesting.rules import required_attribute\n"
            "\n"
            "class User:\n"
            "    __archtest__: Annotated[None, required_attribute("
            '"email", annotation="str", storage="instance")]\n'
            "\n"
            "class Settings:\n"
            "    __archtest__: Annotated[None, required_attribute("
            '"VERSION", annotation="str", storage="class")]\n'
        ),
        encoding="utf-8",
    )
    (target / "reference.py").write_text(
        (
            "class User:\n"
            "    def __init__(self) -> None:\n"
            '        self.email: str = "user@example.com"\n'
            "\n"
            "class Settings:\n"
            "    pass\n"
        ),
        encoding="utf-8",
    )
    return source, target


def _write_constructor_annotation_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "constructor_source"
    target = base / "constructor_target"
    source.mkdir()
    target.mkdir()

    (source / "reference.py").write_text(
        (
            "from typing import Annotated\n"
            "from pythonarchtesting.rules import required_constructor\n"
            "\n"
            "class User:\n"
            "    __archtest__: Annotated[None, required_constructor()]\n"
            "\n"
            "    def __init__(self, name: str) -> None:\n"
            "        self.name = name\n"
            "\n"
            "class Product:\n"
            "    __archtest__: Annotated[None, required_constructor()]\n"
            "\n"
            "    def __init__(self, sku: str) -> None:\n"
            "        self.sku = sku\n"
        ),
        encoding="utf-8",
    )
    (target / "reference.py").write_text(
        (
            "class User:\n"
            "    def __init__(self, name: str) -> None:\n"
            "        self.name = name\n"
            "\n"
            "class Product:\n"
            "    def __init__(self) -> None:\n"
            "        self.sku = ''\n"
        ),
        encoding="utf-8",
    )
    return source, target


def _write_factory_annotation_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "factory_source"
    target = base / "factory_target"
    source.mkdir()
    target.mkdir()

    (source / "reference.py").write_text(
        (
            "from typing import Annotated\n"
            "from pythonarchtesting.rules import required_factory\n"
            "\n"
            "class UserService:\n"
            "    def __init__(self, name: str, value: int):\n"
            "        __archtest__: Annotated[None, required_factory()]\n"
            "        self.name = name\n"
            "        self.value = value\n"
        ),
        encoding="utf-8",
    )
    (target / "reference.py").write_text(
        (
            "class UserService:\n"
            "    def __init__(self, name: str, value: int):\n"
            "        self.name = name\n"
            "        self.value = value\n"
        ),
        encoding="utf-8",
    )
    return source, target


def _write_factory_fail_annotation_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "factory_fail_source"
    target = base / "factory_fail_target"
    source.mkdir()
    target.mkdir()

    (source / "reference.py").write_text(
        (
            "from typing import Annotated\n"
            "from pythonarchtesting.rules import required_factory\n"
            "\n"
            "class UserService:\n"
            "    def __init__(self, name: str):\n"
            "        __archtest__: Annotated[\n"
            "            None,\n"
            "            required_factory(satisfy_with=('classmethod',)),\n"
            "        ]\n"
            "        self.name = name\n"
        ),
        encoding="utf-8",
    )
    (target / "reference.py").write_text(
        (
            "class UserService:\n"
            "    def __init__(self, name: str):\n"
            "        self.name = name\n"
        ),
        encoding="utf-8",
    )
    return source, target


def _write_member_absence_annotation_fixture(base: Path) -> tuple[Path, Path]:
    source = base / "member_absence_source"
    target = base / "member_absence_target"
    source.mkdir()
    target.mkdir()

    (source / "reference.py").write_text(
        (
            "from typing import Annotated\n"
            "from pythonarchtesting.rules import does_not_have\n"
            "\n"
            "class SafeUser:\n"
            '    __archtest__: Annotated[None, does_not_have("debug_dump", member_kind="method")]\n'
            "\n"
            "class UnsafeUser:\n"
            "    __archtest__: Annotated[None, does_not_have("
            '"password", member_kind="attribute", storage="instance")]\n'
        ),
        encoding="utf-8",
    )
    (target / "reference.py").write_text(
        (
            "class SafeUser:\n"
            "    def save(self) -> None:\n"
            "        return None\n"
            "\n"
            "class UnsafeUser:\n"
            "    def __init__(self) -> None:\n"
            '        self.password = "secret"\n'
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
        "API003/required_attribute/v1",
        "API003/required_constructor/v1",
        "API004/required_factory/v1",
        "DEP001/forbid_imports/v2",
        "NEG001/does_not_have/v1",
        "NOM001/subclass_of/v1",
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


def test_flexible_method_annotation_fixture_emits_api002_results(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_flexible_method_annotation_fixture(tmp_path)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "flexible_method_annotation_report.json"

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

    assert exit_code == 1

    report = json.loads(json_out.read_text(encoding="utf-8"))
    results = [
        item
        for target_report in report.get("targets") or []
        for item in target_report.get("results") or []
        if item.get("rule_id") == "API002/required_method/v1"
    ]

    assert len(results) == 3
    assert any(
        item.get("status") == "OK"
        and item.get("details", {}).get("name_match") == "alias"
        and item.get("details", {}).get("resolved_candidate") == "execute"
        for item in results
    )
    assert any(
        item.get("status") == "FAILED"
        and item.get("details", {}).get("name_match") == "regex"
        and item.get("details", {}).get("failure_reason")
        == "multiple_compatible_candidates"
        for item in results
    )
    assert any(
        item.get("status") == "OK"
        and item.get("details", {}).get("name_match") == "any"
        and item.get("details", {}).get("resolved_candidate") == "process"
        for item in results
    )


def test_optional_method_annotation_fixture_emits_expected_statuses(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_optional_method_annotation_fixture(tmp_path)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "optional_method_annotation_report.json"

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

    assert exit_code == 1

    report = json.loads(json_out.read_text(encoding="utf-8"))
    results = [
        item
        for target_report in report.get("targets") or []
        for item in target_report.get("results") or []
        if item.get("rule_id") == "API002/required_method/v1"
    ]

    assert len(results) == 3
    assert any(
        item.get("status") == "OK"
        and item.get("details", {}).get("allow_missing") is True
        for item in results
    )
    assert any(
        item.get("status") == "SKIPPED"
        and item.get("details", {}).get("allow_missing") is True
        and item.get("details", {}).get("reason") == "optional_member_absent"
        for item in results
    )
    assert any(
        item.get("status") == "FAILED"
        and item.get("details", {}).get("allow_missing") is True
        and "parameter annotation mismatch"
        in " ".join(item.get("details", {}).get("errors") or [])
        for item in results
    )


def test_any_params_method_annotation_fixture_emits_expected_statuses(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_any_params_method_annotation_fixture(tmp_path)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "any_params_method_annotation_report.json"

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

    assert exit_code == 1

    report = json.loads(json_out.read_text(encoding="utf-8"))
    results = [
        item
        for target_report in report.get("targets") or []
        for item in target_report.get("results") or []
        if item.get("rule_id") == "API002/required_method/v1"
    ]

    assert len(results) == 2
    assert any(
        item.get("status") == "OK"
        and item.get("details", {}).get("mode") == "any"
        and item.get("details", {}).get("params_ignored") is True
        for item in results
    )
    assert any(
        item.get("status") == "FAILED"
        and item.get("details", {}).get("mode") == "any"
        and item.get("details", {}).get("params_ignored") is True
        and "method kind mismatch"
        in " ".join(item.get("details", {}).get("errors") or [])
        for item in results
    )


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


def test_subclass_annotation_fixture_emits_nominal_type_result(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_subclass_annotation_fixture(tmp_path, inheriting=True)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "subclass_annotation_report.json"

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

    assert [item.get("rule_id") for item in results] == ["NOM001/subclass_of/v1"]
    assert [item.get("status") for item in results] == ["OK"]


def test_subclass_annotation_fixture_reports_failure_for_non_subclass(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_subclass_annotation_fixture(tmp_path, inheriting=False)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "subclass_annotation_failure_report.json"

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

    assert exit_code == 1

    report = json.loads(json_out.read_text(encoding="utf-8"))
    results = [
        item
        for target_report in report.get("targets") or []
        for item in target_report.get("results") or []
    ]

    assert [item.get("rule_id") for item in results] == ["NOM001/subclass_of/v1"]
    assert [item.get("status") for item in results] == ["FAILED"]


def test_attribute_annotation_fixture_emits_attribute_results(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_attribute_annotation_fixture(tmp_path)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "attribute_annotation_report.json"

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

    assert exit_code == 1

    report = json.loads(json_out.read_text(encoding="utf-8"))
    results = [
        item
        for target_report in report.get("targets") or []
        for item in target_report.get("results") or []
        if item.get("rule_id") == "API003/required_attribute/v1"
    ]

    assert sorted(item.get("status") for item in results) == ["FAILED", "OK"]


def test_constructor_annotation_fixture_emits_constructor_results(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_constructor_annotation_fixture(tmp_path)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "constructor_annotation_report.json"

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

    assert exit_code == 1

    report = json.loads(json_out.read_text(encoding="utf-8"))
    results = [
        item
        for target_report in report.get("targets") or []
        for item in target_report.get("results") or []
        if item.get("rule_id") == "API003/required_constructor/v1"
    ]

    assert sorted(item.get("status") for item in results) == ["FAILED", "OK"]


def test_factory_annotation_fixture_emits_factory_result_ok(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_factory_annotation_fixture(tmp_path)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "factory_annotation_report.json"

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

    assert len(results) == 1
    assert results[0].get("rule_id") == "API004/required_factory/v1"
    assert results[0].get("status") == "OK"


def test_factory_fail_annotation_fixture_emits_factory_result_failed(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_factory_fail_annotation_fixture(tmp_path)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "factory_fail_annotation_report.json"

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

    assert exit_code == 1

    report = json.loads(json_out.read_text(encoding="utf-8"))
    results = [
        item
        for target_report in report.get("targets") or []
        for item in target_report.get("results") or []
    ]

    assert len(results) == 1
    assert results[0].get("rule_id") == "API004/required_factory/v1"
    assert results[0].get("status") == "FAILED"
    assert results[0].get("details", {}).get("reason") == "no_factory_candidate_found"


def test_member_absence_annotation_fixture_emits_neg001_results(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(_repo_root())
    source, target = _write_member_absence_annotation_fixture(tmp_path)
    config_path = _write_static_only_config(tmp_path)
    json_out = tmp_path / "member_absence_annotation_report.json"

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

    assert exit_code == 1

    report = json.loads(json_out.read_text(encoding="utf-8"))
    results = [
        item
        for target_report in report.get("targets") or []
        for item in target_report.get("results") or []
        if item.get("rule_id") == "NEG001/does_not_have/v1"
    ]

    assert sorted(item.get("status") for item in results) == ["FAILED", "OK"]


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
    assert target1["summary"]["status_counts"] == {"OK": 8}

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
        and "requests" in item["message"]
        for item in target3["results"]
    )
    assert any(
        item["rule_id"] == "PRO001/implements_protocol/v1"
        and item["status"] == "FAILED"
        and "missing protocol methods: load" in item["message"]
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
            and (
                item["details"].get("match_status") in {"low_confidence", "unmatched"}
                or "missing required method" in str(item["details"].get("reason", ""))
            )
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
