"""Tests for answering several probe requests of one target from one interpreter."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pythonarchtesting.dynamic import batch, probe, runner
from pythonarchtesting.dynamic.runner import (
    ProbeOutcome,
    batch_request,
    batch_timeout,
    can_fork,
    cases_request,
    run_case_batch,
    run_cases,
    run_forked,
)
from pythonarchtesting.dynamic.sandbox import SandboxPolicy
from pythonarchtesting.matching import MatchStatus

_LIMITS = SandboxPolicy(mode="limits")

pytestmark = pytest.mark.skipif(
    not can_fork(_LIMITS), reason="needs fork, memfd_create and an interval timer"
)

_CALC = """
import os
import time

CALLS = []


def double(x):
    CALLS.append(x)
    return x * 2


def seen():
    return len(CALLS)


def leave_a_file():
    with open(os.path.join(os.environ["HOME"], "left.txt"), "w") as f:
        f.write("x")


def home_is_empty():
    if os.listdir(os.environ["HOME"]):
        raise RuntimeError("HOME holds " + ", ".join(os.listdir(os.environ["HOME"])))


def stall():
    while True:
        time.sleep(0.05)


def die():
    print("going", flush=True)
    os._exit(3)
"""

_SHOP = """
from . import calc


def total(x):
    return calc.double(x) + 1
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    package = tmp_path / "forked_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "calc.py").write_text(textwrap.dedent(_CALC), encoding="utf-8")
    (package / "shop.py").write_text(textwrap.dedent(_SHOP), encoding="utf-8")
    return package


def _cases(
    qualname: str, cases: list[dict[str, Any]], module_path: str = "calc"
) -> dict[str, Any]:
    return cases_request(
        module_path=module_path,
        qualname=qualname,
        kind="function",
        cases=cases,
        init=None,
        observe={"calls": True},
    )


def _alone(root: Path, qualname: str, cases: list, timeout_s: float = 5.0) -> Any:
    return run_cases(
        target_root=root,
        module_path="calc",
        qualname=qualname,
        kind="function",
        cases=cases,
        init=None,
        timeout_s=timeout_s,
        sandbox=_LIMITS,
        observe={"calls": True},
    )


def _comparable(outcome: ProbeOutcome) -> dict[str, Any]:
    return {
        "status": outcome.status,
        "cases": outcome.cases,
        "jobs": outcome.jobs,
        "error": outcome.error,
        "stderr": outcome.stderr,
    }


def test_each_request_answers_as_a_probe_of_its_own(root: Path) -> None:
    job = {
        "id": "0",
        "qualname": "double",
        "kind": "function",
        "cases": [{"args": [2]}],
        "init": None,
        "timeout_s": 5.0,
        "observe": {"calls": True},
    }
    jobs = [job, {**job, "id": "1", "qualname": "seen", "cases": [{}]}]
    requests = [
        (_cases("double", [{"args": [1]}, {"args": [2]}]), 5.0),
        (_cases("seen", [{}]), 5.0),
        (batch_request("calc", jobs), batch_timeout(jobs)),
        (_cases("total", [{"args": [1]}], module_path="shop"), 5.0),
    ]

    forked = run_forked(target_root=root, requests=requests, sandbox=_LIMITS)

    alone = [
        _alone(root, "double", [{"args": [1]}, {"args": [2]}]),
        _alone(root, "seen", [{}]),
        run_case_batch(
            target_root=root, module_path="calc", jobs=jobs, sandbox=_LIMITS
        ),
        run_cases(
            target_root=root,
            module_path="shop",
            qualname="total",
            kind="function",
            cases=[{"args": [1]}],
            init=None,
            timeout_s=5.0,
            sandbox=_LIMITS,
            observe={"calls": True},
        ),
    ]
    assert all(outcome is not None for outcome in forked)
    assert [_comparable(o) for o in forked if o] == [_comparable(o) for o in alone]
    # The module is imported afresh for each request: ``seen`` does not see
    # what ``double`` appended in the request before it.
    assert forked[1] is not None
    assert forked[1].cases[0]["status"] == "passed"
    assert forked[2] is not None
    assert forked[2].jobs["1"]["cases"][0]["status"] == "passed"


def test_one_request_crashing_or_overrunning_costs_the_others_nothing(
    root: Path,
) -> None:
    requests = [
        (_cases("die", [{}]), 5.0),
        (_cases("stall", [{}]), 0.5),
        (_cases("double", [{"args": [4]}]), 5.0),
    ]

    died, stalled, doubled = run_forked(
        target_root=root, requests=requests, sandbox=_LIMITS
    )

    assert died is not None
    assert died.status == "crashed"
    assert died.error == "probe exited with code 3 without a result"
    assert stalled is not None
    assert stalled.status == "timeout"
    assert stalled.error == "target did not finish within 0.5 s"
    assert doubled is not None
    assert doubled.status == "completed"
    assert doubled.cases[0]["status"] == "passed"


_NOISY = """
import os
import subprocess
import sys


def raw():
    os.write(1, b"raw to fd 1\\n")
    os.write(2, b"raw to fd 2\\n")
    return 1


def reopened():
    sys.stdout = os.fdopen(1, "w")
    print("printed through a reopened stdout", flush=True)
    return 1


def child():
    subprocess.run(["echo", "echoed by a child process"], check=True)
    return 1
"""


def test_writes_to_the_standard_descriptors_answer_as_a_probe_of_its_own(
    root: Path,
) -> None:
    (root / "noisy.py").write_text(textwrap.dedent(_NOISY), encoding="utf-8")
    names = ["raw", "reopened", "child"]
    job = {
        "id": "0",
        "qualname": "raw",
        "kind": "function",
        "cases": [{}],
        "init": None,
        "timeout_s": 5.0,
        "observe": {},
    }
    jobs = [{**job, "id": str(index), "qualname": n} for index, n in enumerate(names)]
    requests = [
        *[(_cases(name, [{}], module_path="noisy"), 5.0) for name in names],
        (batch_request("noisy", jobs), batch_timeout(jobs)),
    ]

    forked = run_forked(target_root=root, requests=requests, sandbox=_LIMITS)

    alone = [
        run_cases(
            target_root=root,
            module_path="noisy",
            qualname=name,
            kind="function",
            cases=[{}],
            init=None,
            timeout_s=5.0,
            sandbox=_LIMITS,
            observe={"calls": True},
        )
        for name in names
    ]
    alone.append(
        run_case_batch(
            target_root=root, module_path="noisy", jobs=jobs, sandbox=_LIMITS
        )
    )
    assert all(outcome is not None for outcome in forked)
    assert [o.status for o in forked if o] == ["completed"] * 4
    assert [o.cases[0]["status"] for o in forked[:3] if o] == ["passed"] * 3
    assert "raw to fd 1" in (forked[0].stderr if forked[0] else "")
    assert [_comparable(o) for o in forked if o] == [_comparable(o) for o in alone]


def test_each_request_gets_an_empty_home_of_its_own(root: Path) -> None:
    requests = [
        (_cases("leave_a_file", [{}]), 5.0),
        (_cases("home_is_empty", [{}]), 5.0),
    ]

    left, checked = run_forked(target_root=root, requests=requests, sandbox=_LIMITS)

    assert left is not None
    assert "raised" not in left.cases[0]
    assert checked is not None
    assert "raised" not in checked.cases[0]


def test_no_fork_inside_bwrap_and_nothing_answered_then(root: Path) -> None:
    bwrap = SandboxPolicy(mode="bwrap")

    assert can_fork(bwrap) is False
    assert run_forked(
        target_root=root, requests=[(_cases("seen", [{}]), 5.0)] * 2, sandbox=bwrap
    ) == [None, None]


def _ctx(root: Path, rules_by_module: dict[str, list[str]]) -> tuple[Any, list[Any]]:
    sources, targets, matches, rules = {}, {}, {}, []
    for module_path, names in rules_by_module.items():
        for name in names:
            entity_id = f"{module_path}.{name}"
            for kind_of, store in (("s", sources), ("t", targets)):
                store[f"{kind_of}:{entity_id}"] = SimpleNamespace(
                    canonical_id=f"{kind_of}:{entity_id}",
                    kind="function",
                    module_path=module_path,
                    qualname=name.split("#")[0],
                )
            matches[f"s:{entity_id}"] = SimpleNamespace(
                status=MatchStatus.MATCHED, target_id=f"t:{entity_id}"
            )
            rules.append(
                SimpleNamespace(
                    rule_id=f"DYN/runtime_calls/{entity_id}",
                    rule_type="runtime_calls",
                    enabled=True,
                    selector=SimpleNamespace(source_entity_id=f"s:{entity_id}"),
                    params={"cases": [{"args": [1]}], "timeout_s": 5.0},
                )
            )
    ctx = SimpleNamespace(
        target_root=root,
        source_by_id=sources,
        target_by_id=targets,
        matches=matches,
        dynamic_cache={},
        sandbox=_LIMITS,
    )
    return ctx, rules


def _counting_probes(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    started: list[dict[str, Any]] = []
    original = runner._run_probe

    def counting(request: dict[str, Any], **kwargs: Any) -> ProbeOutcome:
        started.append(request)
        return original(request, **kwargs)

    monkeypatch.setattr(runner, "_run_probe", counting)
    return started


def test_prefetch_serves_a_target_from_one_interpreter(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _counting_probes(monkeypatch)
    ctx, rules = _ctx(root, {"calc": ["double", "seen"], "shop": ["total"]})

    batch.prefetch(rules, ctx)

    assert len(started) == 1
    assert started[0]["mode"] == "fork"
    batched = {key[0] for key in ctx.dynamic_cache if key[0]}
    assert batched == {"DYN/runtime_calls/calc.double", "DYN/runtime_calls/calc.seen"}
    key = batch.solo_key(
        module_path="shop",
        qualname="total",
        kind="function",
        cases=[{"args": [1]}],
        init=None,
        timeout_s=5.0,
        observe={"calls": True},
    )
    alone = ctx.dynamic_cache[key]
    assert alone.status == "completed"
    assert [call["module"] for call in alone.cases[0]["calls"]] == ["calc"]


def test_prefetch_runs_a_batch_itself_when_the_fork_gave_no_answer(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        batch, "run_forked", lambda requests, **_: [None] * len(requests)
    )
    ran: list[str] = []
    original = batch.run_case_batch

    def counting(**kwargs: Any) -> ProbeOutcome:
        ran.append(kwargs["module_path"])
        return original(**kwargs)

    monkeypatch.setattr(batch, "run_case_batch", counting)
    ctx, rules = _ctx(root, {"calc": ["double", "seen"], "shop": ["total"]})

    batch.prefetch(rules, ctx)

    assert ran == ["calc"]
    assert {key[0] for key in ctx.dynamic_cache} == {
        "DYN/runtime_calls/calc.double",
        "DYN/runtime_calls/calc.seen",
    }


def test_prefetch_starts_no_server_for_a_single_group(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = _counting_probes(monkeypatch)
    ctx, rules = _ctx(root, {"calc": ["double", "seen"]})

    batch.prefetch(rules, ctx)

    assert [request.get("mode") for request in started] == [None]
    assert len(started[0]["jobs"]) == 2


def test_a_target_module_named_like_a_standard_module_wins_in_a_fork(
    tmp_path: Path,
) -> None:
    # A flat project's ``resource.py``: the fork machinery must not leave the
    # standard ``resource`` (which it uses to limit CPU time) in sys.modules.
    (tmp_path / "resource.py").write_text(
        "class Wood:\n    def amount(self):\n        return 3\n", encoding="utf-8"
    )
    (tmp_path / "game.py").write_text(
        "from resource import Wood\n\n\ndef total():\n    return Wood().amount()\n",
        encoding="utf-8",
    )
    request = cases_request(
        module_path="game",
        qualname="total",
        kind="function",
        cases=[{"args": [], "expect": 3}],
        init=None,
    )

    (forked,) = run_forked(
        target_root=tmp_path, requests=[(request, 5.0)], sandbox=_LIMITS
    )
    alone = run_cases(
        target_root=tmp_path,
        module_path="game",
        qualname="total",
        kind="function",
        cases=[{"args": [], "expect": 3}],
        init=None,
        timeout_s=5.0,
        sandbox=_LIMITS,
    )

    assert alone.status == "completed"
    assert alone.cases[0]["status"] == "passed"
    assert forked is not None
    assert _comparable(forked) == _comparable(alone)


def _children_of(pid: int) -> list[int]:
    found = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", encoding="ascii", errors="replace") as f:
                fields = f.read().rpartition(")")[2].split()
        except OSError:
            continue
        if len(fields) > 1 and fields[1] == str(pid):
            found.append(int(entry))
    return found


def test_a_forked_child_dies_with_the_interpreter_that_forked_it(
    tmp_path: Path,
) -> None:
    (tmp_path / "sleeper.py").write_text(
        "import time\n\n\ndef nap():\n    time.sleep(3600)\n", encoding="utf-8"
    )
    target_root, package = runner.import_target_spec(tmp_path)
    request = cases_request(
        module_path="sleeper", qualname="nap", kind="function", cases=[{}], init=None
    )
    entry = {
        "request": {**request, "target_root": str(target_root), "package": package},
        "timeout_s": 60.0,
        "cpu_s": 61,
    }
    served = {"mode": "fork", "module_path": "", "requests": [entry], "cases": []}
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    with tempfile.TemporaryFile() as stdin:
        stdin.write(json.dumps(served).encode("utf-8"))
        stdin.seek(0)
        server = subprocess.Popen(  # pylint: disable=consider-using-with
            [sys.executable, "-s", "-B", str(runner.PROBE_PATH)],
            stdin=stdin,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(target_root),
            env=env,
            start_new_session=True,
        )
    children: list[int] = []
    deadline = time.monotonic() + 10
    while not children and time.monotonic() < deadline:
        children = _children_of(server.pid)
        time.sleep(0.05)
    # Give the child time to import the target and start sleeping.
    time.sleep(0.5)
    os.killpg(server.pid, signal.SIGKILL)  # what the runner's overall timeout does
    server.wait()

    assert children
    survivors = []
    deadline = time.monotonic() + 5
    for child in children:
        while os.path.exists(f"/proc/{child}") and time.monotonic() < deadline:
            time.sleep(0.05)
        if os.path.exists(f"/proc/{child}"):
            survivors.append(child)
            os.kill(child, signal.SIGKILL)
    assert not survivors


def test_await_child_keeps_a_status_reaped_just_before_the_alarm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pid = os.fork()
    if pid == 0:
        os._exit(3)
    real_waitpid = os.waitpid

    def waitpid_then_alarm(wanted: int, options: int) -> tuple[int, int]:
        reaped = real_waitpid(wanted, options)
        # SIGALRM arriving after the child is reaped, before the status is kept.
        signal.getsignal(signal.SIGALRM)(signal.SIGALRM, None)
        return reaped

    monkeypatch.setattr(probe.os, "waitpid", waitpid_then_alarm)

    status, timed_out = probe._await_child(pid, 5.0)

    assert status is not None
    assert os.waitstatus_to_exitcode(status) == 3
    assert not timed_out


_SPAWNER = """
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def _note(pid):
    with open(os.path.join(HERE, "spawned.pid"), "a") as f:
        f.write(f"{pid}\\n")


def spawn():
    _note(subprocess.Popen(["sleep", "60"]).pid)
    while True:
        time.sleep(0.05)


def fork():
    pid = os.fork()
    if pid == 0:
        time.sleep(60)
        os._exit(0)
    _note(pid)
    while True:
        time.sleep(0.05)
"""


def _spawned(root: Path, wait_s: float = 10.0) -> list[int]:
    """The pids the target noted, once it has noted one.

    The target opens the file before it writes the pid, so the file can exist
    and still be empty: wait for a whole line, not for the file.
    """
    path = root / "spawned.pid"
    deadline = time.monotonic() + wait_s
    while True:
        text = path.read_text(encoding="ascii") if path.exists() else ""
        if text.endswith("\n") or time.monotonic() >= deadline:
            return [int(line) for line in text.split()]
        time.sleep(0.05)


def _running(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/stat", encoding="ascii", errors="replace") as f:
            return f.read().rpartition(")")[2].split()[0] != "Z"
    except (OSError, IndexError):
        return False


def _survivors(pids: list[int], wait_s: float = 5.0) -> list[int]:
    """The pids still running after ``wait_s``; those are killed here."""
    deadline = time.monotonic() + wait_s
    while any(_running(pid) for pid in pids) and time.monotonic() < deadline:
        time.sleep(0.05)
    left = [pid for pid in pids if _running(pid)]
    for pid in left:
        os.kill(pid, signal.SIGKILL)
    return left


@pytest.mark.parametrize("qualname", ["spawn", "fork"])
def test_what_an_overrunning_request_started_ends_with_it(
    root: Path, qualname: str
) -> None:
    (root / "spawner.py").write_text(textwrap.dedent(_SPAWNER), encoding="utf-8")
    requests = [
        (_cases(qualname, [{}], module_path="spawner"), 1.0),
        (_cases("double", [{"args": [4]}]), 5.0),
    ]

    overran, doubled = run_forked(target_root=root, requests=requests, sandbox=_LIMITS)

    assert overran is not None
    assert overran.status == "timeout"
    assert doubled is not None
    assert doubled.status == "completed"
    assert not _survivors(_spawned(root), wait_s=0.5)


def _start_server(target_root: Path, entry: dict[str, Any]) -> subprocess.Popen:
    """The forking interpreter for ``entry``, as the runner would start it."""
    served = {"mode": "fork", "module_path": "", "requests": [entry], "cases": []}
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    with tempfile.TemporaryFile() as stdin:
        stdin.write(json.dumps(served).encode("utf-8"))
        stdin.seek(0)
        return subprocess.Popen(  # pylint: disable=consider-using-with
            [sys.executable, "-s", "-B", str(runner.PROBE_PATH)],
            stdin=stdin,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(target_root),
            env=env,
            start_new_session=True,
        )


@pytest.mark.parametrize("qualname", ["spawn", "fork"])
def test_what_a_request_started_dies_with_the_interpreter_that_forked_it(
    root: Path, qualname: str
) -> None:
    (root / "spawner.py").write_text(textwrap.dedent(_SPAWNER), encoding="utf-8")
    target_root, package = runner.import_target_spec(root)
    request = _cases(qualname, [{}], module_path="spawner")
    server = _start_server(
        target_root,
        {
            "request": {**request, "target_root": str(target_root), "package": package},
            "timeout_s": 60.0,
            "cpu_s": 61,
        },
    )
    spawned = _spawned(root)
    os.killpg(server.pid, signal.SIGKILL)  # what the runner's overall timeout does
    server.wait()

    assert spawned
    assert not _survivors(spawned)


def test_a_combined_answer_over_the_file_size_limit_is_run_again_alone(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each answer fits under ``RLIMIT_FSIZE``, all of them together do not:
    the forking interpreter cannot write its response, every request is left
    unanswered, and each runs again in a probe of its own."""
    for name in ("wordy", "verbose"):
        (root / f"{name}.py").write_text(
            "def say(n):\n    raise ValueError('x' * 400_000)\n", encoding="utf-8"
        )
    small = SandboxPolicy(mode="limits", file_size_mb=1)
    answered: list[list[ProbeOutcome | None]] = []
    original = batch.run_forked

    def recording(**kwargs: Any) -> list[ProbeOutcome | None]:
        answered.append(original(**kwargs))
        return answered[-1]

    monkeypatch.setattr(batch, "run_forked", recording)
    ctx, rules = _ctx(root, {"wordy": ["say", "say#2"], "verbose": ["say"]})
    ctx.sandbox = small

    batch.prefetch(rules, ctx)

    assert answered == [[None, None]]
    key = ("DYN/runtime_calls/wordy.say", "s:wordy.say", "t:wordy.say")
    jobs = ctx.dynamic_cache[key].cases
    assert jobs[0]["raised"] == "ValueError: " + "x" * 400_000
    alone = run_cases(
        target_root=root,
        module_path="verbose",
        qualname="say",
        kind="function",
        cases=[{"args": [1]}],
        init=None,
        timeout_s=5.0,
        sandbox=small,
        observe={"calls": True},
    )
    assert alone.status == "completed"
