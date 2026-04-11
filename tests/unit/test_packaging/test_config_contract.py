from pathlib import Path


def test_repo_root_does_not_ship_user_override_config_files() -> None:
    assert not Path(".pythonarchtesting").exists()
    assert not Path("python_arch_testing.conf").exists()
    assert not Path("custom_config.conf").exists()
    assert not Path("defaults.conf").exists()
