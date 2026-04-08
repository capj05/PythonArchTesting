from pathlib import Path


def test_removed_legacy_files_are_absent():
    repo_root = Path(__file__).resolve().parents[3]

    package_root = repo_root / "src" / "pythonarchtesting"

    assert not (package_root / "config" / "config_backup.py").exists()
    assert not (package_root / "rules_original.py").exists()
