import subprocess
import sys


def _import_ok(module_name: str) -> bool:
    code = f"import importlib; importlib.import_module('{module_name}'); print('OK')"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
    )
    return result.returncode == 0 and "OK" in result.stdout


def test_removed_legacy_modules_not_importable():
    code = """
import importlib
for name in (
    "pythonarchtesting.api",
    "pythonarchtesting.cli_lazy",
    "pythonarchtesting.runner_parallel",
    "pythonarchtesting.config.config",
    "pythonarchtesting.config.schema",
    "pythonarchtesting.state.project_state.discovery_bridge",
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


def test_public_config_and_cli_imports_work():
    assert _import_ok("pythonarchtesting.config")
    assert _import_ok("pythonarchtesting.config.loader")
    assert _import_ok("pythonarchtesting.cli")
