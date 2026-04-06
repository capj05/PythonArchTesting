from pathlib import Path


def _dependency_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_requirements_files_exist_and_match_documented_plain_requirements_strategy():
    required_files = [
        Path("requirements.txt"),
        Path("requirements-dev.txt"),
    ]
    docs = Path("docs/dependency-management.md").read_text(encoding="utf-8").lower()

    assert "intentionally maintained without hashes" in docs

    for requirements_file in required_files:
        assert (
            requirements_file.exists()
        ), f"Missing requirements file: {requirements_file}"
        assert _dependency_lines(
            requirements_file
        ), f"Requirements file has no installable entries: {requirements_file}"
