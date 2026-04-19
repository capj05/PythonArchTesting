import importlib


def test_public_config_and_cli_imports_work() -> None:
    importlib.import_module("pythonarchtesting.config")
    importlib.import_module("pythonarchtesting.config.loader")
    importlib.import_module("pythonarchtesting.cli")
    importlib.import_module("pythonarchtesting.run_state")
    importlib.import_module("pythonarchtesting.runner")
