import subprocess
import sys


def _import_ok(module_name: str) -> bool:
    code = f"import importlib; importlib.import_module('{module_name}'); print('OK')"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
    )
    return result.returncode == 0 and "OK" in result.stdout


def test_public_config_and_cli_imports_work():
    assert _import_ok("pythonarchtesting.config")
    assert _import_ok("pythonarchtesting.config.loader")
    assert _import_ok("pythonarchtesting.cli")
