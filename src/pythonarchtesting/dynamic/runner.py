"""Run dynamic checks against a target in an isolated interpreter.

Target code is executed only here, in a child process started with ``-I`` (no
``PYTHONPATH``, no user site-packages) and ``-B`` (no bytecode written into the
project), in its own process group, with a wall-clock timeout. How much more
it is confined depends on the ``SandboxPolicy`` (see ``dynamic.sandbox``).
"""

from __future__ import annotations

import json
import os
import signal
import subprocess  # nosec B404 - executing the target is the purpose of this module
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

from .sandbox import SandboxPolicy, interpreter_paths

# Resolved, so the path stays valid inside bwrap, which only binds real paths;
# the package may have been imported through e.g. "tests/fixtures/../../src".
PROBE_PATH = Path(__file__).resolve().with_name("probe.py")
_STDERR_TAIL = 2000


@dataclass(frozen=True)
class ProbeOutcome:
    """What one probe run reported back.

    ``status`` is ``completed`` when every case ran (each case carries its own
    verdict), or one of ``import_error``, ``timeout``, ``crashed`` when the
    cases could not run at all.
    """

    status: str
    cases: list[dict[str, Any]] = field(default_factory=list)
    imports: list[dict[str, Any]] = field(default_factory=list)
    jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    error: str | None = None
    stderr: str = ""


def import_target_spec(target_root: Path) -> tuple[Path, str | None]:
    """Return the resolved root and the package name it is imported under.

    A root with an ``__init__.py`` is itself a package and is imported by name,
    so its relative imports work; any other root is put on ``sys.path`` as is.
    """
    root = target_root.resolve()
    package = root.name if (root / "__init__.py").is_file() else None
    return root, package


_NO_SANDBOX = SandboxPolicy(mode="none")
_SIGNAL_CAUSES = {
    # No SIGXFSZ: CPython ignores it, so a write over the file size limit
    # raises OSError (EFBIG) in the target instead of killing the probe.
    "SIGXCPU": "CPU time limit",
    "SIGKILL": "killed",
    "SIGSEGV": "segmentation fault",
}


def _exit_description(returncode: int) -> str:
    if returncode >= 0:
        return f"probe exited with code {returncode} without a result"
    try:
        name = signal.Signals(-returncode).name
    except ValueError:
        return f"probe was killed by signal {-returncode}"
    cause = _SIGNAL_CAUSES.get(name)
    return f"probe was killed by {name}" + (f" ({cause})" if cause else "")


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    """Kill the child and everything it started, not only the child itself."""
    if hasattr(os, "killpg"):
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except (ProcessLookupError, PermissionError):
            pass
    process.kill()


@dataclass(frozen=True)
class _Exchange:
    stdout: str
    stderr: str
    timed_out: bool
    returncode: int


def _tail(handle: IO[bytes], limit: int) -> str:
    size = handle.seek(0, os.SEEK_END)
    handle.seek(max(0, size - limit))
    return handle.read().decode("utf-8", errors="replace")


def _exchange(
    command: list[str],
    *,
    request: str,
    cwd: Path,
    policy: SandboxPolicy,
    home: Path,
    timeout_s: float,
) -> _Exchange:
    """Run the probe with files, not pipes, for its stdin, stdout, and stderr.

    Processes the target starts inherit those descriptors. With pipes, one
    that outlives the probe — say it detached with ``setsid`` and the probe
    was killed on timeout before it could end it — keeps them open and the
    parent waits for it. A file has
    no reader to block, so the run ends when the probe does.
    """
    with (
        tempfile.TemporaryFile() as stdin,
        tempfile.TemporaryFile() as stdout,
        tempfile.TemporaryFile() as stderr,
    ):
        stdin.write(request.encode("utf-8"))
        stdin.seek(0)
        process = subprocess.Popen(  # nosec B603 - fixed argv, no shell
            command,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            cwd=str(cwd),
            env=policy.environment(home),
            preexec_fn=policy.preexec(timeout_s),  # noqa: PLW1509
            start_new_session=hasattr(os, "setsid"),
        )
        timed_out = False
        try:
            process.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            # The probe and whatever is left in its process group go together.
            _kill_group(process)
            process.wait()
        stdout.seek(0)
        return _Exchange(
            stdout=stdout.read().decode("utf-8", errors="replace"),
            stderr=_tail(stderr, _STDERR_TAIL),
            timed_out=timed_out,
            returncode=process.returncode,
        )


def _run_probe(
    request: dict[str, Any],
    *,
    target_root: Path,
    timeout_s: float,
    sandbox: SandboxPolicy | None = None,
) -> ProbeOutcome:
    policy = sandbox or _NO_SANDBOX
    root, package = import_target_spec(target_root)
    request = {**request, "target_root": str(root), "package": package}
    # -B: never write __pycache__ into the analysed project.
    argv = [sys.executable, "-I", "-B", str(PROBE_PATH)]
    with tempfile.TemporaryDirectory(prefix="pat-home-") as home:
        exchange = _exchange(
            policy.wrap(argv, visible=[root, *interpreter_paths()], cwd=root),
            request=json.dumps(request),
            cwd=root,
            policy=policy,
            home=Path(home),
            timeout_s=timeout_s,
        )
    stderr = exchange.stderr
    if exchange.timed_out:
        return ProbeOutcome(
            status="timeout",
            error=f"target did not finish within {timeout_s:g} s",
            stderr=stderr,
        )
    try:
        response = json.loads(exchange.stdout)
    except json.JSONDecodeError:
        return ProbeOutcome(
            status="crashed",
            error=_exit_description(exchange.returncode),
            stderr=stderr,
        )
    return ProbeOutcome(
        status=str(response.get("status", "crashed")),
        cases=list(response.get("cases") or []),
        imports=list(response.get("imports") or []),
        jobs=dict(response.get("jobs") or {}),
        error=response.get("error"),
        stderr=stderr,
    )


def run_cases(
    *,
    target_root: Path,
    module_path: str,
    qualname: str,
    kind: str,
    cases: list[dict[str, Any]],
    init: dict[str, Any] | None,
    timeout_s: float,
    sandbox: SandboxPolicy | None = None,
    observe: dict[str, Any] | None = None,
) -> ProbeOutcome:
    """Call the target once per case; ``observe`` picks what each case reports.

    ``{"calls": True}`` adds the calls the target's module made into other
    modules, ``{"calls": "edges"}`` every call between two project modules,
    ``{"writes": True}`` the attribute assignments made from outside the
    owning class, and ``{"instances": True}`` the project classes that
    project code instantiated.
    """
    request = {
        "module_path": module_path,
        "qualname": qualname,
        "kind": kind,
        "cases": cases,
        "init": init,
        "observe": observe or {},
    }
    return _run_probe(
        request, target_root=target_root, timeout_s=timeout_s, sandbox=sandbox
    )


# Head-room for interpreter start-up and the module import, which the per-job
# deadlines inside the child do not cover.
_BATCH_STARTUP_S = 5.0


def run_case_batch(
    *,
    target_root: Path,
    module_path: str,
    jobs: list[dict[str, Any]],
    sandbox: SandboxPolicy | None = None,
) -> ProbeOutcome:
    """Run the cases of several rules on one module in a single interpreter.

    Each job is ``{"id", "qualname", "kind", "cases", "init", "timeout_s",
    "observe"}``.
    The child bounds every job by its own ``timeout_s`` where the platform has
    an interval timer, so one slow job does not starve the rest; the whole
    batch is additionally bounded by the sum of the job timeouts.
    ``ProbeOutcome.jobs`` maps each job id to ``{"status", "cases", "error"}``.
    """
    timeout_s = _BATCH_STARTUP_S + sum(float(job["timeout_s"]) for job in jobs)
    request = {"module_path": module_path, "jobs": jobs, "cases": []}
    return _run_probe(
        request, target_root=target_root, timeout_s=timeout_s, sandbox=sandbox
    )


def run_import_check(
    *,
    target_root: Path,
    module_path: str,
    forbidden: list[str],
    allow: list[str],
    timeout_s: float,
    sandbox: SandboxPolicy | None = None,
) -> ProbeOutcome:
    """Import one target module and report the forbidden imports its code made.

    ``ProbeOutcome.imports`` lists each offending import with the module name,
    the importing file relative to the target root, and the line.
    """
    request = {
        "mode": "imports",
        "module_path": module_path,
        "forbidden": forbidden,
        "allow": allow,
        "cases": [],
    }
    return _run_probe(
        request, target_root=target_root, timeout_s=timeout_s, sandbox=sandbox
    )


__all__ = [
    "PROBE_PATH",
    "ProbeOutcome",
    "import_target_spec",
    "run_cases",
    "run_case_batch",
    "run_import_check",
]
