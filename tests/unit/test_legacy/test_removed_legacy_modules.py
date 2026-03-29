import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "src.config.config_backup",
        "src.config.config",
        "src.api",
        "src.cli_lazy",
        "src.runner_parallel",
        "src.rules_original",
        "src.pat_rules",
        "src.config.schema",
        "src.state.project_state.discovery_bridge",
    ],
)
def test_removed_legacy_modules_are_not_importable(module_name: str):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
