"""Confinement for the child interpreters that run target code.

Three modes, chosen with ``--sandbox``:

``none``
    The child inherits the caller's environment and limits. Isolation is a
    separate process and a wall-clock timeout, nothing more.
``limits`` (default)
    POSIX resource limits on the child (address space, CPU time, size of
    files it writes, open files, no core dumps), a scrubbed environment with a
    throw-away ``HOME``, and its own process group so a timeout also kills the
    processes it started. Available wherever the ``resource`` module is.
``bwrap``
    ``limits`` plus bubblewrap: no network, its own PID namespace, the whole
    file system read-only, and only the system directories, the Python
    installation, the framework, and the analysed project visible; ``/tmp`` is
    an empty in-memory directory. Requires ``bwrap`` and unprivileged user
    namespaces.

None of these is a substitute for running untrusted code on a machine that
holds nothing of value; ``bwrap`` comes closest.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess  # nosec B404 - probing bwrap is part of choosing the sandbox
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

SANDBOX_MODES = ("none", "limits", "bwrap")
DEFAULT_SANDBOX_MODE = "limits"

_MIB = 1024 * 1024
_BWRAP_HOME = "/tmp/home"  # nosec B108 - inside the sandbox's private tmpfs
_NPROC_HEADROOM = 256  # tasks a child may add to the user's current count
_STACK_MB = 8  # a child's stack, and so each of its threads' stacks
_SYSTEM_DIRS = ("/usr", "/etc", "/opt")
_SYSTEM_LINKS = ("/bin", "/sbin", "/lib", "/lib64", "/lib32")


class SandboxUnavailableError(RuntimeError):
    """The requested sandbox cannot run on this machine."""


@dataclass(frozen=True)
class SandboxPolicy:
    """How a child interpreter is confined; built once per run."""

    mode: str = DEFAULT_SANDBOX_MODE
    memory_mb: int = 1024
    file_size_mb: int = 16
    open_files: int = 256
    tmp_size_mb: int = 64

    def __post_init__(self) -> None:
        if self.mode not in SANDBOX_MODES:
            raise ValueError(f"unknown sandbox mode {self.mode!r}")
        if self.memory_mb <= 0:
            raise ValueError("memory_mb must be positive")

    @property
    def confined(self) -> bool:
        return self.mode != "none"

    def environment(self, home: Path) -> dict[str, str] | None:
        """The child's environment; ``None`` keeps the caller's (mode ``none``)."""
        if not self.confined:
            return None
        # Inside bwrap the host's temporary directory does not exist; HOME is
        # created on the sandbox's own /tmp instead (see wrap()).
        inside = _BWRAP_HOME if self.mode == "bwrap" else str(home)
        return {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "HOME": inside,
            "TMPDIR": inside,
            # Fewer malloc arenas: each reserves address space per thread.
            "MALLOC_ARENA_MAX": "2",
        }

    def preexec(self, timeout_s: float) -> Callable[[], None] | None:
        """Resource limits applied in the child before it executes Python."""
        if not self.confined:
            return None
        try:
            import resource
        except ImportError:  # pragma: no cover - Windows
            return None

        cpu_s = math.ceil(timeout_s) + 1
        # RLIMIT_DATA rather than RLIMIT_AS: both stop large allocations, but
        # RLIMIT_AS also counts address space merely reserved per thread and
        # capped a target at ~37 threads under 1 GiB (RLIMIT_DATA: ~126).
        memory_limit = getattr(resource, "RLIMIT_DATA", resource.RLIMIT_AS)
        limits: tuple[tuple[int, int], ...] = (
            (memory_limit, self.memory_mb * _MIB),
            # glibc sizes every thread's stack by RLIMIT_STACK, and RLIMIT_DATA
            # counts those stacks: a host with a 16 MiB stack left a target
            # ~60 threads. 8 MiB is the usual Linux default.
            (resource.RLIMIT_STACK, _STACK_MB * _MIB),
            (resource.RLIMIT_CPU, cpu_s),
            (resource.RLIMIT_FSIZE, self.file_size_mb * _MIB),
            (resource.RLIMIT_NOFILE, self.open_files),
            (resource.RLIMIT_CORE, 0),
        )
        # RLIMIT_NPROC caps the tasks (processes and threads) of the whole
        # user, not of the child, so it is set above what the user already
        # runs; the headroom bounds a fork bomb and still allows threads.
        tasks = _user_task_count()
        if tasks is not None and hasattr(resource, "RLIMIT_NPROC"):
            limits += ((resource.RLIMIT_NPROC, tasks + _NPROC_HEADROOM),)

        def apply() -> None:
            for which, value in limits:
                _, hard = resource.getrlimit(which)
                if hard != resource.RLIM_INFINITY:
                    value = min(value, hard)
                resource.setrlimit(which, (value, value))

        return apply

    def wrap(self, argv: list[str], *, visible: list[Path], cwd: Path) -> list[str]:
        """Prefix ``argv`` with bubblewrap in mode ``bwrap``; else return it as is."""
        if self.mode != "bwrap":
            return argv
        command = [
            _bwrap_path(),
            "--unshare-all",
            "--die-with-parent",
            "--new-session",
            "--cap-drop",
            "ALL",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            # A bounded private tmpfs: its pages do not count against the
            # memory rlimit, so without a size it could fill the host's RAM.
            "--size",
            str(self.tmp_size_mb * _MIB),
            "--tmpfs",
            "/tmp",  # nosec B108 - a private tmpfs inside the sandbox
            "--dir",
            _BWRAP_HOME,
        ]
        for directory in _SYSTEM_DIRS:
            if os.path.isdir(directory):
                command += ["--ro-bind", directory, directory]
        for link in _SYSTEM_LINKS:
            if os.path.islink(link):
                command += ["--symlink", os.readlink(link), link]
            elif os.path.isdir(link):
                command += ["--ro-bind", link, link]
        for source, dest in _bind_pairs(visible):
            command += ["--ro-bind", source, dest]
        command += ["--chdir", str(cwd), "--"]
        return command + argv


def _user_task_count() -> int | None:
    """Tasks of the current user, as RLIMIT_NPROC counts them; None off Linux."""
    proc = Path("/proc")
    if not proc.is_dir():
        return None
    uid = os.getuid()
    count = 0
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != uid:
                continue
            count += sum(1 for _ in (entry / "task").iterdir())
        except OSError:
            continue  # the process ended meanwhile
    return count


def _bind_pairs(paths: list[Path]) -> list[tuple[str, str]]:
    """The read-only binds that make existing ``paths`` visible, as
    ``(source, destination)``, outermost destination first, without one
    already covered by another or by a system directory.

    Each path's real directory is bound where it really is and, when the path
    reaches it through a symlink, also under the path as named: a venv behind
    a symlinked directory is started by its unresolved ``sys.executable``.
    """
    pairs: dict[Path, Path] = {}
    for path in paths:
        if not os.path.exists(path):
            continue
        real = Path(os.path.realpath(path))
        pairs.setdefault(real, real)
        pairs.setdefault(Path(os.path.abspath(path)), real)
    kept: list[tuple[str, str]] = []
    covered: list[Path] = []
    for dest in sorted(pairs, key=lambda p: len(p.parts)):
        if any(dest == parent or parent in dest.parents for parent in covered):
            continue
        if any(str(dest).startswith(system + os.sep) for system in _SYSTEM_DIRS):
            continue
        covered.append(dest)
        kept.append((str(pairs[dest]), str(dest)))
    return kept


def _bwrap_path() -> str:
    path = shutil.which("bwrap")
    if path is None:
        raise SandboxUnavailableError("bwrap is not installed")
    return path


def interpreter_paths() -> list[Path]:
    """Directories the child interpreter needs to see to start at all."""
    import pythonarchtesting

    framework = Path(pythonarchtesting.__file__).resolve().parent.parent
    executable = Path(sys.executable)
    return [
        Path(sys.prefix),
        Path(sys.base_prefix),
        Path(sys.exec_prefix),
        executable.parent,
        executable.resolve().parent,
        framework,
    ]


def check_available(policy: SandboxPolicy) -> None:
    """Fail early, with the reason, when ``policy`` cannot run here.

    The check starts an interpreter exactly as a real run would — same
    wrapper, environment, and resource limits — so a limit that breaks
    start-up is caught here rather than reported as a failing target.
    """
    if not policy.confined:
        return
    probe = policy.wrap(
        [sys.executable, "-I", "-c", "pass"],
        visible=interpreter_paths(),
        cwd=Path("/"),
    )
    try:
        completed = subprocess.run(  # nosec B603 - fixed argv, no shell
            probe,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=policy.environment(Path(tempfile.gettempdir())),
            preexec_fn=policy.preexec(30),  # noqa: PLW1509
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SandboxUnavailableError(f"{policy.mode} could not start: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()[-1:] or ["no detail"]
        raise SandboxUnavailableError(
            f"{policy.mode} could not start a Python interpreter: {detail[0]}"
        )


__all__ = [
    "DEFAULT_SANDBOX_MODE",
    "SANDBOX_MODES",
    "SandboxPolicy",
    "SandboxUnavailableError",
    "check_available",
    "interpreter_paths",
]
