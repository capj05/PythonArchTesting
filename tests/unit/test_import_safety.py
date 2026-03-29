"""CLI import safety and startup budget regression checks."""

from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys


def _run_cli_help_module_capture() -> list[str]:
    code = """
import json
import sys
import src.cli
try:
    src.cli.main(["--help"])
except SystemExit:
    pass
print(json.dumps({"mods": sorted(sys.modules.keys())}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"CLI --help failed: {result.stderr}"
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    return list(payload["mods"])


def _cli_importtime_us(stderr_text: str) -> int:
    matches = re.findall(
        r"import time:\s+\d+\s+\|\s+(\d+)\s+\|\s+src\.cli",
        stderr_text,
    )
    assert matches, f"Could not find src.cli importtime line in stderr:\n{stderr_text}"
    return int(matches[-1])


def test_cli_help_import_safety():
    """CLI --help must not import optional DB modules."""
    mods = _run_cli_help_module_capture()
    assert not any(m.startswith("sqlalchemy") for m in mods)
    assert "src.runner_multi" not in mods
    assert not any(m.startswith("src.runner_multi.") for m in mods)
    assert "src.state.project_state" not in mods
    assert not any(m.startswith("src.state.project_state.") for m in mods)


def test_cli_help_importtime_budget():
    """CLI --help median startup cost must stay under the budget."""
    cumulative_us = []
    for _ in range(5):
        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "importtime",
                "-c",
                "import src.cli; src.cli.main(['--help'])",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"CLI --help failed: {result.stderr}"
        cumulative_us.append(_cli_importtime_us(result.stderr))

    median_us = int(statistics.median(cumulative_us))
    assert median_us <= 300000, (
        "CLI --help importtime budget exceeded: "
        f"median={median_us}us, samples={cumulative_us}, budget=300000us"
    )
