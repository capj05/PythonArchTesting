from __future__ import annotations

from pathlib import Path

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.evidence.collection import (
    collect_static_evidence,
    parse_python_modules,
)


def test_parse_python_modules_collects_syntax_errors(tmp_path: Path):
    cfg = create_config_from_dict({})
    (tmp_path / "good.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("def broken(:\n", encoding="utf-8")

    parsed, errors = parse_python_modules(
        root_path=tmp_path,
        config=cfg,
        target_module_name=None,
    )

    assert [module.module_path for module in parsed] == ["good"]
    assert len(errors) == 1
    assert errors[0][0].name == "bad.py"


def test_collect_static_evidence_uses_direct_ast_parsing(tmp_path: Path):
    cfg = create_config_from_dict({})
    (tmp_path / "app.py").write_text(
        "import os\n\n\ndef run():\n    return os.system('echo test')\n",
        encoding="utf-8",
    )

    evidence = collect_static_evidence(
        root_path=tmp_path,
        config=cfg,
        target_module_name=None,
    )

    assert evidence["modules"] == ["app"]
    assert [edge["module"] for edge in evidence["import_edges"]] == ["os"]
    assert any(site["callee"] == "os.system" for site in evidence["call_sites"])
