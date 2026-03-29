import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "mypy_scoped_gate.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("mypy_scoped_gate", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module spec from {SCRIPT_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_rollout_targets_ignores_comments_blanks_and_duplicates(
    tmp_path: Path,
):
    module = _load_module()
    manifest = tmp_path / "targets.txt"
    manifest.write_text(
        "\n".join(
            [
                "",
                "   # comment",
                "src/constants",
                "src/constants",
                "   ",
                "src/exceptions.py",
            ]
        ),
        encoding="utf-8",
    )

    targets = module.load_rollout_targets(manifest)

    assert targets == ["src/constants", "src/exceptions.py"]


def test_main_rejects_empty_manifest(tmp_path: Path, monkeypatch, capsys):
    module = _load_module()
    (tmp_path / "src").mkdir()
    manifest = tmp_path / "targets.txt"
    manifest.write_text("# comment only\n\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = module.main(["--targets-file", str(manifest.name)])

    assert exit_code == 2
    stderr = capsys.readouterr().err
    assert "No targets found in manifest" in stderr


def test_main_rejects_target_outside_src(tmp_path: Path, monkeypatch, capsys):
    module = _load_module()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "constants").mkdir()
    outside_target = tmp_path / "outside.py"
    outside_target.write_text("", encoding="utf-8")
    manifest = tmp_path / "targets.txt"
    manifest.write_text(
        "\n".join(["src/constants", "outside.py"]),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    exit_code = module.main(["--targets-file", str(manifest.name)])

    assert exit_code == 2
    stderr = capsys.readouterr().err
    assert "Configured target must be inside src/: outside.py" in stderr


def test_main_invokes_mypy_in_manifest_order_and_returns_subprocess_code(
    tmp_path: Path, monkeypatch
):
    module = _load_module()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "constants").mkdir()
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "exceptions.py").write_text("", encoding="utf-8")
    (src_dir / "state_multi.py").write_text("", encoding="utf-8")
    manifest = tmp_path / "targets.txt"
    manifest.write_text(
        "\n".join(
            [
                "src/constants",
                "src/__init__.py",
                "src/exceptions.py",
                "src/state_multi.py",
                "src/constants",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    recorded = {}

    def _fake_run(command):
        recorded["command"] = command
        return subprocess.CompletedProcess(command, returncode=7)

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    exit_code = module.main(["--targets-file", str(manifest.name)])

    assert exit_code == 7
    command = recorded["command"]
    assert command[0:3] == [sys.executable, "-m", "mypy"]
    assert command[3:7] == [
        "src/constants",
        "src/__init__.py",
        "src/exceptions.py",
        "src/state_multi.py",
    ]
    assert command[-4:] == [
        "--ignore-missing-imports",
        "--follow-imports=skip",
        "--show-error-codes",
        "--no-incremental",
    ]
