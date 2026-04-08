from pathlib import Path


def test_pyproject_python_compatibility_metadata_is_consistent() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'requires-python = ">=3.10"' in text
    assert "Programming Language :: Python :: 3.8" not in text
    assert "Programming Language :: Python :: 3.9" not in text
    assert "target-version = ['py310']" in text
    assert 'python_version = "3.10"' in text
