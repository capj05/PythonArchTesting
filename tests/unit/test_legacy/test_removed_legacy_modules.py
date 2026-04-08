import importlib

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
        "pythonarchtesting.state.project_state.discovery_bridge",
    ],
)
def test_removed_legacy_modules_are_not_importable(module_name: str):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
