from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_python_code(
    code: str, *, cwd: Path | None = None, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    """Run Python code in a fresh interpreter rooted at the repository."""
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd or PROJECT_ROOT),
    )


def run_python_json(code: str, *, cwd: Path | None = None, timeout: int = 30) -> Any:
    """Run Python code and parse the last non-empty stdout line as JSON."""
    result = run_python_code(code, cwd=cwd, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"Python subprocess failed: {result.stderr}")

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("Python subprocess produced no JSON output")

    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse JSON output: {exc}") from exc


def capture_module_imports(
    target_module: str,
    *,
    cwd: Path | None = None,
    timeout: int = 30,
    extra_sys_path: Path | None = None,
) -> list[str]:
    """Import a module in a fresh interpreter and return loaded module names."""
    extra_path_setup = ""
    if extra_sys_path is not None:
        extra_path_setup = f"sys.path.insert(0, {str(extra_sys_path)!r})\n"

    payload = run_python_json(
        "\n".join(
            [
                "import importlib",
                "import json",
                "import sys",
                extra_path_setup.rstrip(),
                f"importlib.import_module({target_module!r})",
                "print(json.dumps(sorted(sys.modules.keys())))",
            ]
        ),
        cwd=cwd,
        timeout=timeout,
    )
    if not isinstance(payload, list):
        raise RuntimeError("Expected imported module payload to be a JSON list")

    return [str(name) for name in payload]
