from pathlib import Path


def test_dependency_management_uses_pyproject_as_single_source_of_truth():
    docs = Path("docs/dependency-management.md").read_text(encoding="utf-8").lower()

    assert not Path("requirements.txt").exists()
    assert not Path("requirements-dev.txt").exists()
    assert "edit dependencies only in `pyproject.toml`" in docs
    assert "intentionally maintained without hashes" not in docs
