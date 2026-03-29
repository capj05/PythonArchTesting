from pathlib import Path


def test_lockfiles_exist_and_include_hashes():
    required = [
        Path("requirements.txt"),
        Path("requirements-dev.txt"),
    ]

    for lockfile in required:
        assert lockfile.exists(), f"Missing lockfile: {lockfile}"
        content = lockfile.read_text(encoding="utf-8")
        assert "--hash=" in content, f"Lockfile is not hash-pinned: {lockfile}"
