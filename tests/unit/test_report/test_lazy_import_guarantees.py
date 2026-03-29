from __future__ import annotations

import json
import subprocess
import sys


def _run_capture(code: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def test_importing_cli_does_not_import_db_or_concrete_generators():
    code = """
import json
import sys
import src.cli
mods = sorted(sys.modules.keys())
print(json.dumps({"mods": mods}))
"""
    payload = _run_capture(code)
    mods = payload["mods"]

    concrete = {
        "src.report.json_generator",
        "src.report.markdown_generator",
    }
    assert not any(m.startswith("sqlalchemy") for m in mods)
    assert not concrete.intersection(set(mods))


def test_help_path_does_not_import_db_or_concrete_generators():
    code = """
import json
import sys
import src.cli
try:
    src.cli.main(["--help"])
except SystemExit:
    pass
mods = sorted(sys.modules.keys())
print(json.dumps({"mods": mods}))
"""
    payload = _run_capture(code)
    mods = payload["mods"]

    concrete = {
        "src.report.json_generator",
        "src.report.markdown_generator",
    }
    assert not any(m.startswith("sqlalchemy") for m in mods)
    assert not concrete.intersection(set(mods))
