from pathlib import Path


def test_removed_legacy_files_are_absent():
    repo_root = Path(__file__).resolve().parents[3]

    assert not (repo_root / "src" / "config" / "config_backup.py").exists()
    assert not (repo_root / "src" / "rules_original.py").exists()
