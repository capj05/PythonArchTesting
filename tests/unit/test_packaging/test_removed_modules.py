from __future__ import annotations

import importlib
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "pythonarchtesting.config.config_backup",
        "pythonarchtesting.config.config",
        "pythonarchtesting.api",
        "pythonarchtesting.cli_lazy",
        "pythonarchtesting.runner_parallel",
        "pythonarchtesting.rules_original",
        "pythonarchtesting.pat_rules",
        "pythonarchtesting.config.schema",
        "pythonarchtesting.state.project_state",
        "pythonarchtesting.state.project_state.discovery_bridge",
        "pythonarchtesting.state.state",
        "pythonarchtesting.runner_multi.runner_multi",
    ],
)
def test_removed_modules_are_not_importable(module_name: str):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


def test_removed_module_subprocess_contract() -> None:
    code = """
import importlib
for name in (
    "pythonarchtesting.api",
    "pythonarchtesting.cli_lazy",
    "pythonarchtesting.runner_parallel",
    "pythonarchtesting.config.config",
    "pythonarchtesting.config.schema",
    "pythonarchtesting.state.project_state",
    "pythonarchtesting.state.project_state.discovery_bridge",
    "pythonarchtesting.state.state",
    "pythonarchtesting.runner_multi.runner_multi",
):
    try:
        importlib.import_module(name)
        print("BAD", name)
    except ModuleNotFoundError:
        print("OK", name)
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0
    assert "BAD" not in result.stdout
