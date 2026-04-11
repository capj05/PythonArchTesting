from pathlib import Path


def test_repo_root_exposes_only_canonical_auto_discovery_config() -> None:
    assert Path("python_arch_testing.conf").exists()
    assert not Path("custom_config.conf").exists()
