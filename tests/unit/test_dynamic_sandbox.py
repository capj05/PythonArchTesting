"""Tests that the sandbox modes actually confine target code."""

from __future__ import annotations

import os
import sys
import textwrap
import time
from pathlib import Path

import pytest

from pythonarchtesting.dynamic.runner import run_cases
from pythonarchtesting.dynamic.sandbox import (
    SandboxPolicy,
    SandboxUnavailableError,
    check_available,
)

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX limits")

_HOSTILE = """
import os
import socket
import subprocess


# Cases only drive execution, so each function prints what it found; the
# probe hands the target's output back as stderr.
def show(label, value):
    print(f"{label}={value!r}", flush=True)


def read(path):
    with open(path, encoding="utf-8") as handle:
        show("read", handle.read())


def write_here(size):
    with open("written.bin", "wb") as handle:
        handle.write(b"x" * size)


def allocate(megabytes):
    block = bytearray(megabytes * 1024 * 1024)
    show("allocated", len(block))


def env(name):
    show("env", os.environ.get(name))


def home():
    show("home", os.environ.get("HOME"))


def connect():
    socket.create_connection(("192.0.2.1", 9), timeout=1).close()
    show("connected", True)


def orphan():
    child = subprocess.Popen(["sleep", "300"])
    show("pid", child.pid)


def detached():
    child = subprocess.Popen(["sleep", "300"], start_new_session=True)
    show("pid", child.pid)


def threads(count):
    import threading

    event = threading.Event()
    started = []
    for _ in range(count):
        thread = threading.Thread(target=event.wait)
        thread.start()
        started.append(thread)
    event.set()
    show("threads", len(started))


def home_is_writable():
    path = os.path.join(os.environ["HOME"], ".cache")
    os.makedirs(path)
    show("writable", os.path.isdir(path))


def fill_tmp(megabytes):
    for index in range(megabytes):
        with open(f"/tmp/fill{index}", "wb") as handle:
            handle.write(b"x" * 1024 * 1024)


def nproc():
    import resource

    show("nproc", resource.getrlimit(resource.RLIMIT_NPROC)[0])
"""


def _bwrap_works() -> bool:
    try:
        check_available(SandboxPolicy(mode="bwrap"))
    except SandboxUnavailableError:
        return False
    return True


needs_bwrap = pytest.mark.skipif(not _bwrap_works(), reason="bwrap unavailable")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    package = tmp_path / "hostile_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "evil.py").write_text(textwrap.dedent(_HOSTILE), encoding="utf-8")
    return package


def _call(
    root: Path, qualname: str, args: list, mode: str, **policy: int
) -> tuple[dict, str]:
    outcome = run_cases(
        target_root=root,
        module_path="evil",
        qualname=qualname,
        kind="function",
        cases=[{"args": args}],
        init=None,
        timeout_s=10,
        sandbox=SandboxPolicy(mode=mode, **policy),
    )
    assert outcome.status == "completed", (outcome.error, outcome.stderr)
    case = outcome.cases[0]
    assert case["status"] == "passed", case["failures"]
    return case, outcome.stderr


def _pid(stderr: str) -> int:
    return int(stderr.rsplit("pid=", 1)[1].split()[0])


def test_unknown_mode_is_rejected() -> None:
    with pytest.raises(ValueError):
        SandboxPolicy(mode="docker")


@posix_only
def test_limits_scrub_the_environment(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAT_TEST_SECRET", "hunter2")

    _, confined = _call(root, "env", ["PAT_TEST_SECRET"], "limits")
    _, open_run = _call(root, "env", ["PAT_TEST_SECRET"], "none")
    _, home = _call(root, "home", [], "limits")

    assert "env=None" in confined
    assert "env='hunter2'" in open_run
    assert f"home={os.environ.get('HOME')!r}" not in home


@posix_only
def test_limits_cap_memory(root: Path) -> None:
    case, stderr = _call(root, "allocate", [512], "limits", memory_mb=256)

    assert case["raised"].startswith("MemoryError")
    assert "allocated=" not in stderr


@posix_only
def test_limits_cap_written_file_size(root: Path) -> None:
    case, _ = _call(root, "write_here", [2 * 1024 * 1024], "limits", file_size_mb=1)

    assert "File too large" in case["raised"]


@posix_only
def test_processes_left_behind_are_killed(root: Path) -> None:
    _, stderr = _call(root, "orphan", [], "limits")
    pid = _pid(stderr)

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    os.kill(pid, 9)
    pytest.fail("the target's child process outlived the probe")


@needs_bwrap
def test_bwrap_hides_files_outside_the_project(root: Path, tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("private", encoding="utf-8")

    hidden, hidden_out = _call(root, "read", [str(secret)], "bwrap")
    _, visible_out = _call(root, "read", [str(secret)], "limits")

    assert hidden["raised"].startswith("FileNotFoundError")
    assert "private" not in hidden_out
    assert "read='private'" in visible_out


@needs_bwrap
def test_bwrap_makes_the_project_read_only(root: Path) -> None:
    case, _ = _call(root, "write_here", [10], "bwrap")

    assert "Read-only file system" in case["raised"]
    assert not (root / "written.bin").exists()


@needs_bwrap
def test_bwrap_cuts_the_network(root: Path) -> None:
    case, stderr = _call(root, "connect", [], "bwrap")

    assert "raised" in case
    assert "connected=" not in stderr


@needs_bwrap
def test_bwrap_can_still_read_the_project(root: Path) -> None:
    case, stderr = _call(root, "read", [str(root / "__init__.py")], "bwrap")

    assert "raised" not in case
    assert "read=''" in stderr


def test_no_bytecode_is_written_into_the_project(root: Path) -> None:
    _call(root, "env", ["X"], "none")

    assert not (root / "__pycache__").exists()


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc tasks")
def test_limits_cap_processes_above_what_the_user_already_runs(root: Path) -> None:
    import resource

    _, stderr = _call(root, "nproc", [], "limits")
    limit = int(stderr.split("nproc=")[1].split()[0])

    assert limit != resource.RLIM_INFINITY
    assert limit > _user_task_count_now()


def _user_task_count_now() -> int:
    from pythonarchtesting.dynamic import sandbox

    count = sandbox._user_task_count()
    assert count is not None and count > 0
    return count


@posix_only
def test_a_detached_process_does_not_hold_up_the_run(root: Path) -> None:
    started = time.monotonic()
    _, stderr = _call(root, "detached", [], "limits")
    elapsed = time.monotonic() - started
    pid = _pid(stderr)
    try:
        os.kill(pid, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    if alive:
        os.kill(pid, 9)

    assert elapsed < 5
    if sys.platform.startswith("linux"):
        # The probe adopts what detaches and ends it before exiting.
        assert not alive


@posix_only
def test_limits_leave_room_for_a_thread_pool(root: Path) -> None:
    case, stderr = _call(root, "threads", [64], "limits")

    assert "raised" not in case
    assert "threads=64" in stderr


@needs_bwrap
def test_bwrap_home_exists_and_is_writable(root: Path) -> None:
    case, stderr = _call(root, "home_is_writable", [], "bwrap")

    assert "raised" not in case
    assert "writable=True" in stderr


@needs_bwrap
def test_bwrap_tmp_is_bounded(root: Path) -> None:
    case, _ = _call(root, "fill_tmp", [100], "bwrap")

    assert "No space left on device" in case["raised"]


def _binds(command: list[str]) -> list[tuple[str, str]]:
    return [
        (command[index + 1], command[index + 2])
        for index, arg in enumerate(command)
        if arg == "--ro-bind"
    ]


@posix_only
def test_bwrap_binds_a_path_reached_through_a_symlink_where_it_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A venv reached through a symlinked directory is started by its
    unresolved path, so the real directory is also bound under that path."""
    from pythonarchtesting.dynamic import sandbox

    monkeypatch.setattr(sandbox, "_bwrap_path", lambda: "bwrap")
    real = tmp_path / "real_venv" / "bin"
    real.mkdir(parents=True)
    link = tmp_path / "venv"
    link.symlink_to(tmp_path / "real_venv")

    command = SandboxPolicy(mode="bwrap").wrap(
        ["python"], visible=[link / "bin"], cwd=Path("/")
    )

    assert (str(real), str(real)) in _binds(command)
    assert (str(real), str(link / "bin")) in _binds(command)


@posix_only
def test_bwrap_binds_a_resolved_path_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pythonarchtesting.dynamic import sandbox

    monkeypatch.setattr(sandbox, "_bwrap_path", lambda: "bwrap")
    (tmp_path / "project" / "pkg").mkdir(parents=True)

    command = SandboxPolicy(mode="bwrap").wrap(
        ["python"],
        visible=[tmp_path / "project", tmp_path / "project" / "pkg"],
        cwd=Path("/"),
    )

    project = str(tmp_path / "project")
    assert [bind for bind in _binds(command) if tmp_path.name in bind[1]] == [
        (project, project)
    ]
