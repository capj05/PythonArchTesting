"""Run dynamic checks against a target in an isolated interpreter.

Target code is executed only here, in a child process started with ``-s`` (no
user site-packages) and ``-B`` (no bytecode written into the project), in an
environment stripped of every ``PYTHON*`` variable but a fixed
``PYTHONHASHSEED``, in its own process group, with a wall-clock timeout. How much more
it is confined depends on the ``SandboxPolicy`` (see ``dynamic.sandbox``).
"""

from __future__ import annotations

import ast
import copy
import json
import math
import os
import select
import signal
import subprocess  # nosec B404 - executing the target is the purpose of this module
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

from pythonarchtesting.constants import FileConstants

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


# ``path -> ((mtime, size), deepest level)`` of the files ``_imports_relatively``
# has read: a file is parsed again only when it changes.
_RELATIVE_LEVELS: dict[str, tuple[tuple[int, int], int]] = {}
_RELATIVE_LEVELS_KEPT = 4096


def _relative_level(path: Path) -> int:
    """The deepest level of a relative import in the file at ``path`` (``0``
    for none, or a file that does not decode or parse)."""
    try:
        stat = path.stat()
    except OSError:
        return 0
    key, stamp = str(path), (stat.st_mtime_ns, stat.st_size)
    known = _RELATIVE_LEVELS.get(key)
    if known is not None and known[0] == stamp:
        return known[1]
    try:
        # From bytes, as Python reads a module: a BOM or a coding line holds.
        tree = ast.parse(path.read_bytes())
    except (SyntaxError, ValueError, OSError):
        level = 0
    else:
        level = max(
            (n.level for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)),
            default=0,
        )
    if len(_RELATIVE_LEVELS) >= _RELATIVE_LEVELS_KEPT:
        _RELATIVE_LEVELS.clear()
    _RELATIVE_LEVELS[key] = (stamp, level)
    return level


def _imports_relatively(root: Path) -> bool:
    """Whether a module under ``root`` imports relatively up to ``root``.

    ``from .x`` directly in ``root``, or ``from ..x`` in ``root/domain/``:
    such a module only runs inside a package, so a beginner who left out the
    ``__init__.py`` still meant the directory as one. A relative import that
    stays inside a subpackage (``from .x`` in ``domain/``) needs only the
    subpackage. Hidden directories, ``__pycache__`` and virtual environments
    (``FileConstants.EXCLUDED_DIRS``) are not looked into; a file that does
    not parse says nothing either way. What a file imports is remembered
    while it stays unchanged, as each run of a task asks again.
    """
    for directory, subdirectories, files in os.walk(root):
        subdirectories[:] = sorted(
            name
            for name in subdirectories
            if not name.startswith(".") and name not in FileConstants.EXCLUDED_DIRS
        )
        depth = len(Path(directory).relative_to(root).parts)
        for name in sorted(files):
            if name.endswith(".py") and _relative_level(Path(directory) / name) > depth:
                return True
    return False


def import_target_spec(target_root: Path) -> tuple[Path, str | None]:
    """Return the resolved root and the package name it is imported under.

    A root with an ``__init__.py`` is itself a package and is imported by name,
    so its relative imports work. So is a root without one whose modules
    import relatively up to it (a package whose ``__init__.py`` was left
    out); the probe then stands in an empty package for it. Its name need not
    be an identifier (``05capj_capsky``, ``capj05-capsky``): the import
    system finds the directory by name all the same, and the static side
    judges such a root as a package too. Any other root is put on
    ``sys.path`` as is.
    """
    root = target_root.resolve()
    if (root / "__init__.py").is_file() or _imports_relatively(root):
        return root, root.name
    return root, None


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


def _child_environment(policy: SandboxPolicy, home: Path) -> dict[str, str]:
    """The policy's environment with no ``PYTHON*`` variable but a fixed hash seed.

    ``-I`` would drop ``PYTHONPATH`` and friends, but also ``PYTHONHASHSEED``:
    with a random seed the order a target iterates a set of strings in, and so
    the order of the calls it makes, changes from run to run.
    """
    base = policy.environment(home)
    environment = dict(os.environ if base is None else base)
    for name in [name for name in environment if name.startswith("PYTHON")]:
        del environment[name]
    environment["PYTHONHASHSEED"] = "0"
    return environment


def _outlives(process: subprocess.Popen[bytes], timeout_s: float) -> bool:
    """Wait until ``process`` ends; ``True`` when it still runs after ``timeout_s``.

    ``Popen.wait`` with a timeout polls, sleeping up to 50 ms between looks,
    so a probe that ends after 70 ms is noticed only after about 110 ms.
    Where Linux offers a descriptor for the process (``pidfd_open``), the
    wait ends as the process does; elsewhere ``Popen.wait`` waits. The
    process is not reaped here.
    """
    pidfd_open = getattr(os, "pidfd_open", None)
    if pidfd_open is not None:
        try:
            descriptor = pidfd_open(process.pid)
        except OSError:
            descriptor = None
        if descriptor is not None:
            try:
                poller = select.poll()
                poller.register(descriptor, select.POLLIN)
                return not poller.poll(max(0, math.ceil(timeout_s * 1000)))
            finally:
                os.close(descriptor)
    try:
        process.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return True
    return False


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
            env=_child_environment(policy, home),
            preexec_fn=policy.preexec(timeout_s),  # noqa: PLW1509
            start_new_session=hasattr(os, "setsid"),
        )
        try:
            timed_out = _outlives(process, timeout_s)
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
    # -s: no user site-packages; -B: never write __pycache__ into the analysed
    # project. Not -I, which would ignore PYTHONHASHSEED (_child_environment).
    argv = [sys.executable, "-s", "-B", str(PROBE_PATH)]
    with tempfile.TemporaryDirectory(prefix="pat-home-") as home:
        exchange = _exchange(
            policy.wrap(argv, visible=[root, *interpreter_paths()], cwd=root),
            request=json.dumps(request),
            cwd=root,
            policy=policy,
            home=Path(home),
            timeout_s=timeout_s,
        )
    return _outcome(exchange, timeout_s)


def _outcome(exchange: _Exchange, timeout_s: float) -> ProbeOutcome:
    """What a probe run that took ``timeout_s`` at most reported back."""
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
    request = cases_request(
        module_path=module_path,
        qualname=qualname,
        kind=kind,
        cases=cases,
        init=init,
        observe=observe,
    )
    return _run_probe(
        request, target_root=target_root, timeout_s=timeout_s, sandbox=sandbox
    )


def run_reference_cases(
    runs: dict[str, ProbeOutcome] | None, **kwargs: Any
) -> ProbeOutcome:
    """``run_cases(**kwargs)`` on the reference, once per request in ``runs``.

    The reference does the same on the same cases whatever target it is
    compared with, so every target of a run shares one outcome per distinct
    request (``runs`` lives as long as the run). Each caller gets its own copy.
    """
    if runs is None:
        return run_cases(**kwargs)
    key = json.dumps(
        {name: value for name, value in kwargs.items() if name != "sandbox"},
        sort_keys=True,
        default=str,
    ) + repr(kwargs.get("sandbox"))
    if key not in runs:
        runs[key] = run_cases(**kwargs)
    return copy.deepcopy(runs[key])


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
    timeout_s = batch_timeout(jobs)
    request = batch_request(module_path, jobs)
    return _run_probe(
        request, target_root=target_root, timeout_s=timeout_s, sandbox=sandbox
    )


def batch_timeout(jobs: list[dict[str, Any]]) -> float:
    """The time ``run_case_batch`` gives a batch of ``jobs`` as a whole."""
    return _BATCH_STARTUP_S + sum(float(job["timeout_s"]) for job in jobs)


def batch_request(module_path: str, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """The request ``run_case_batch`` sends the probe."""
    return {"module_path": module_path, "jobs": jobs, "cases": []}


def cases_request(
    *,
    module_path: str,
    qualname: str,
    kind: str,
    cases: list[dict[str, Any]],
    init: dict[str, Any] | None,
    observe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The request ``run_cases`` sends the probe."""
    return {
        "module_path": module_path,
        "qualname": qualname,
        "kind": kind,
        "cases": cases,
        "init": init,
        "observe": observe or {},
    }


def can_fork(sandbox: SandboxPolicy | None) -> bool:
    """Whether ``run_forked`` can run requests here under ``sandbox``.

    It needs ``fork``, ``memfd_create`` and an interval timer (Linux), and
    is not used inside ``bwrap``: each probe there gets a file system of its
    own (an empty ``/tmp``), which the forks of one interpreter would share.
    """
    policy = sandbox or _NO_SANDBOX
    return (
        policy.mode != "bwrap"
        and hasattr(os, "fork")
        and hasattr(os, "memfd_create")
        and hasattr(signal, "setitimer")
    )


# Head-room for the start-up of the interpreter that forks the requests.
_FORK_STARTUP_S = 5.0


def run_forked(
    *,
    target_root: Path,
    requests: list[tuple[dict[str, Any], float]],
    sandbox: SandboxPolicy | None = None,
) -> list[ProbeOutcome | None]:
    """Run several probe requests on one target from a single interpreter.

    Each ``(request, timeout_s)`` is what ``_run_probe`` would be given for
    a probe of its own (``batch_request``, ``cases_request``). The probe
    starts once, imports nothing of the target, and forks a child per
    request; the child takes its own standard streams, CPU limit and,
    under ``limits``, an empty ``HOME`` of its own, then answers the
    request as a probe of its own would, so it sees the target as freshly
    imported, and it is killed with whatever it started when it overruns
    ``timeout_s``. The children stay in the forking interpreter's process
    group, so overrunning ``_FORK_STARTUP_S`` plus the sum of the timeouts
    kills them and what they started together with it. Each outcome is the
    one ``_run_probe`` makes of that child's output. ``None`` in place of an
    outcome means the request got no answer here (``can_fork`` false, or the
    forking interpreter itself failed, say its combined response ran over
    ``RLIMIT_FSIZE``): its caller runs it on its own.
    """
    if not requests or not can_fork(sandbox):
        return [None] * len(requests)
    policy = sandbox or _NO_SANDBOX
    root, package = import_target_spec(target_root)
    entries = [
        {
            "request": {**request, "target_root": str(root), "package": package},
            "timeout_s": float(timeout_s),
            # As ``SandboxPolicy.preexec`` sets it for a probe of its own.
            "cpu_s": math.ceil(timeout_s) + 1 if policy.confined else None,
        }
        for request, timeout_s in requests
    ]
    total = _FORK_STARTUP_S + sum(float(timeout_s) for _, timeout_s in requests)
    served = _run_probe(
        {
            "mode": "fork",
            "module_path": "",
            "requests": entries,
            "own_home": policy.confined,
            "cases": [],
        },
        target_root=target_root,
        timeout_s=total,
        sandbox=sandbox,
    )
    outcomes: list[ProbeOutcome | None] = []
    for index, (_, timeout_s) in enumerate(requests):
        answer = served.jobs.get(str(index)) if served.status == "completed" else None
        if not isinstance(answer, dict) or answer.get("retry"):
            outcomes.append(None)
            continue
        exchange = _Exchange(
            stdout=str(answer.get("stdout", "")),
            stderr=str(answer.get("stderr", "")),
            timed_out=bool(answer.get("timed_out")),
            returncode=int(answer.get("returncode", 0)),
        )
        outcomes.append(_outcome(exchange, float(timeout_s)))
    return outcomes


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
    "batch_request",
    "batch_timeout",
    "can_fork",
    "cases_request",
    "import_target_spec",
    "run_cases",
    "run_case_batch",
    "run_forked",
    "run_import_check",
    "run_reference_cases",
]
