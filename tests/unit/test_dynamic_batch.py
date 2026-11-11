"""Tests for running several rules of one module in a single interpreter."""

from __future__ import annotations

import signal
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from pythonarchtesting.dynamic import batch
from pythonarchtesting.dynamic.runner import ProbeOutcome, run_case_batch
from pythonarchtesting.matching import MatchStatus

_SOURCE = """
import json
import time

CALLS = []


class Point:
    def __init__(self):
        self.x = 0


def double(x):
    CALLS.append(x)
    return x * 2


def report(_unused=None):
    # Calls into json only when an earlier job left state behind.
    if CALLS:
        return json.dumps(CALLS)
    return ""


def move(point):
    point.x = 1


def stall():
    while True:
        time.sleep(0.05)
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    package = tmp_path / "batch_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "calc.py").write_text(textwrap.dedent(_SOURCE), encoding="utf-8")
    return package


def _job(
    job_id: str,
    qualname: str,
    cases: list,
    timeout_s: float = 5.0,
    observe: dict | None = None,
) -> dict:
    return {
        "id": job_id,
        "qualname": qualname,
        "kind": "function",
        "cases": cases,
        "init": None,
        "timeout_s": timeout_s,
        "observe": observe if observe is not None else {"calls": True},
    }


def test_jobs_share_one_interpreter_and_module_state(root: Path) -> None:
    outcome = run_case_batch(
        target_root=root,
        module_path="calc",
        jobs=[
            _job("0", "double", [{"args": [2]}]),
            _job("1", "report", [{}]),
        ],
    )

    assert outcome.status == "completed"
    assert {key: job["status"] for key, job in outcome.jobs.items()} == {
        "0": "completed",
        "1": "completed",
    }
    calls = outcome.jobs["1"]["cases"][0]["calls"]
    assert [call["module"] for call in calls] == ["json"]


def test_each_job_observes_what_its_rule_needs(root: Path) -> None:
    point = {"$new": "Point"}
    outcome = run_case_batch(
        target_root=root,
        module_path="calc",
        jobs=[
            _job("0", "move", [{"args": [point]}], observe={"writes": True}),
            _job("1", "move", [{"args": [point]}], observe={"calls": True}),
            _job("2", "move", [{"args": [point]}], observe={"writes": True}),
        ],
    )

    first, calls_only, second = (outcome.jobs[key]["cases"][0] for key in "012")
    assert [(w["class"], w["writer"]) for w in first["writes"]] == [
        ("Point", "calc:move")
    ]
    assert "writes" not in calls_only
    assert calls_only["calls"] == []
    # The recorder is shared by the batch but starts afresh for every job.
    assert second["writes"] == first["writes"]


def test_observation_follows_the_rule_type() -> None:
    assert batch.observation(SimpleNamespace(rule_type="runtime_writes")) == {
        "writes": True
    }
    assert batch.observation(SimpleNamespace(rule_type="runtime_calls", params={})) == {
        "calls": True
    }
    assert batch.observation(
        SimpleNamespace(rule_type="runtime_calls", params={"transitive": True})
    ) == {"calls": "transitive"}
    assert batch.observation(
        SimpleNamespace(rule_type="runtime_instances", params={})
    ) == {"instances": True}
    assert batch.observation(
        SimpleNamespace(rule_type="runtime_instances", params={"transitive": True})
    ) == {"instances": "transitive"}


_SHOP = """
from .repo import Repo


def build():
    return Repo()
"""

_REPO = """
class Repo:
    def __init__(self):
        self.items = []
"""


def test_instance_and_call_jobs_share_a_batch(root: Path) -> None:
    (root / "shop.py").write_text(textwrap.dedent(_SHOP), encoding="utf-8")
    (root / "repo.py").write_text(textwrap.dedent(_REPO), encoding="utf-8")
    outcome = run_case_batch(
        target_root=root,
        module_path="shop",
        jobs=[
            _job("0", "build", [{}], observe={"instances": True}),
            _job("1", "build", [{}], observe={"calls": True}),
            _job("2", "build", [{}], observe={"instances": True}),
        ],
    )

    first, calls_only, second = (outcome.jobs[key]["cases"][0] for key in "012")
    assert [(i["module"], i["class"], i["creator"]) for i in first["instances"]] == [
        ("repo", "Repo", "shop:build")
    ]
    # The constructor wrappers left by the first job do not hide the
    # constructor call from forbid_runtime_calls.
    assert "instances" not in calls_only
    assert [(c["module"], c["callee"]) for c in calls_only["calls"]] == [
        ("repo", "Repo.__init__")
    ]
    # The recorder is shared by the batch but starts afresh for every job.
    assert second["instances"] == first["instances"]


def test_a_wrapped_constructor_still_owns_its_attribute_writes(root: Path) -> None:
    (root / "shop.py").write_text(textwrap.dedent(_SHOP), encoding="utf-8")
    (root / "repo.py").write_text(textwrap.dedent(_REPO), encoding="utf-8")
    outcome = run_case_batch(
        target_root=root,
        module_path="shop",
        jobs=[
            _job("0", "build", [{}], observe={"instances": True}),
            _job("1", "build", [{}], observe={"writes": True}),
        ],
    )

    # Repo.__init__ sets its own attribute; the instance recorder's wrapper
    # around it must not make that look like a write from outside.
    assert outcome.jobs["1"]["cases"][0]["writes"] == []


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="needs an interval timer")
def test_a_stalled_job_times_out_alone(root: Path) -> None:
    outcome = run_case_batch(
        target_root=root,
        module_path="calc",
        jobs=[
            _job("0", "stall", [{}], timeout_s=0.5),
            _job("1", "double", [{"args": [3]}]),
        ],
    )

    assert outcome.status == "completed"
    assert outcome.jobs["0"]["status"] == "timeout"
    assert outcome.jobs["1"]["cases"][0]["status"] == "passed"


def _ctx(
    root: Path, module_path: str, names: list[str], rule_type: str = "runtime_calls"
) -> tuple[SimpleNamespace, list[SimpleNamespace]]:
    sources, targets, matches, rules = {}, {}, {}, []
    for name in names:
        source = SimpleNamespace(
            canonical_id=f"s:{name}",
            kind="function",
            module_path=module_path,
            qualname=name,
        )
        target = SimpleNamespace(
            canonical_id=f"t:{name}",
            kind="function",
            module_path=module_path,
            qualname=name,
        )
        sources[source.canonical_id] = source
        targets[target.canonical_id] = target
        matches[source.canonical_id] = SimpleNamespace(
            status=MatchStatus.MATCHED, target_id=target.canonical_id
        )
        rules.append(
            SimpleNamespace(
                rule_id=f"DYN/{rule_type}/{name}",
                rule_type=rule_type,
                enabled=True,
                selector=SimpleNamespace(source_entity_id=source.canonical_id),
                params={"cases": [{"args": [1]}], "timeout_s": 5.0},
            )
        )
    ctx = SimpleNamespace(
        target_root=root,
        source_by_id=sources,
        target_by_id=targets,
        matches=matches,
        dynamic_cache={},
    )
    return ctx, rules


def test_prefetch_batches_two_or_more_rules_per_module(root: Path) -> None:
    ctx, rules = _ctx(root, "calc", ["double", "report"])
    write_ctx, write_rules = _ctx(root, "calc", ["move"], "runtime_writes")
    ctx.source_by_id.update(write_ctx.source_by_id)
    ctx.target_by_id.update(write_ctx.target_by_id)
    ctx.matches.update(write_ctx.matches)

    batch.prefetch(rules + write_rules, ctx)

    assert len(ctx.dynamic_cache) == 3
    cached = {key[0]: outcome for key, outcome in ctx.dynamic_cache.items()}
    assert {outcome.status for outcome in cached.values()} == {"completed"}
    assert [
        c["module"] for c in cached["DYN/runtime_calls/report"].cases[0]["calls"]
    ] == ["json"]
    # move(1) raises on the int argument, which is reported, not cached as error.
    moved = cached["DYN/runtime_writes/move"].cases[0]
    assert moved["writes"] == []
    assert moved["raised"].startswith("AttributeError")


def test_prefetch_leaves_a_single_rule_to_run_alone(root: Path) -> None:
    ctx, rules = _ctx(root, "calc", ["double"])

    batch.prefetch(rules, ctx)

    assert ctx.dynamic_cache == {}


def test_prefetch_caches_an_import_failure_for_every_rule(root: Path) -> None:
    (root / "calc.py").write_text("raise RuntimeError('broken')\n", encoding="utf-8")
    ctx, rules = _ctx(root, "calc", ["double", "report"])

    batch.prefetch(rules, ctx)

    assert {outcome.status for outcome in ctx.dynamic_cache.values()} == {
        "import_error"
    }


def test_prefetch_falls_back_when_the_whole_batch_fails(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        batch,
        "run_case_batch",
        lambda **_: ProbeOutcome(status="timeout", error="whole batch hung"),
    )
    ctx, rules = _ctx(root, "calc", ["double", "report"])

    batch.prefetch(rules, ctx)

    assert ctx.dynamic_cache == {}


def test_prefetch_skips_rules_that_are_not_plainly_matched(root: Path) -> None:
    ctx, rules = _ctx(root, "calc", ["double", "report"])
    ctx.matches["s:double"].status = MatchStatus.UNMATCHED
    rules.append(SimpleNamespace(rule_type="runtime_imports", enabled=True))

    batch.prefetch(rules, ctx)

    assert ctx.dynamic_cache == {}


def test_observation_of_the_class_rule_types() -> None:
    def rule(rule_type: str, **params: object) -> SimpleNamespace:
        return SimpleNamespace(rule_type=rule_type, params=params)

    assert batch.observation(rule("runtime_members", names=["x", "y"])) == {
        "names": ["x", "y"]
    }
    assert batch.observation(rule("runtime_class_kind", expect="concrete")) == {
        "construct": True
    }
    assert batch.observation(rule("runtime_class_kind", expect="abstract")) == {
        "construct": False
    }
    assert batch.observation(
        rule("runtime_protocol", attributes=["name"], methods={"export": 1})
    ) == {"names": ["name"], "callables": {"export": 1}}


def test_class_jobs_share_a_batch_with_function_jobs(root: Path) -> None:
    point_job = {**_job("0", "Point", [{}]), "kind": "class"}
    outcome = run_case_batch(
        target_root=root,
        module_path="calc",
        jobs=[
            {**point_job, "observe": {"names": ["x", "y"]}},
            {**point_job, "id": "1", "observe": {"construct": False}},
            _job("2", "double", [{"args": [2]}]),
        ],
    )

    assert outcome.status == "completed"
    members = outcome.jobs["0"]["cases"][0]
    assert members["constructed"] is True
    assert members["members"] == {
        "x": {"present": True, "where": "instance"},
        "y": {"present": False},
    }
    kind = outcome.jobs["1"]["cases"][0]
    assert kind["abstract"] is False
    assert "constructed" not in kind
    assert outcome.jobs["2"]["status"] == "completed"


def test_prefetch_batches_class_rules(root: Path) -> None:
    ctx, rules = _ctx(root, "calc", ["Point"], "runtime_members")
    # Both rules sit on the same class, so one context describes them.
    _, kind_rules = _ctx(root, "calc", ["Point"], "runtime_class_kind")
    for entity in [*ctx.source_by_id.values(), *ctx.target_by_id.values()]:
        entity.kind = "class"
    rules[0].params = {"cases": [{}], "names": ["x"]}
    kind_rules[0].params = {"cases": [{}], "expect": "concrete"}

    batch.prefetch(rules + kind_rules, ctx)

    cached = {key[0]: outcome for key, outcome in ctx.dynamic_cache.items()}
    assert set(cached) == {
        "DYN/runtime_members/Point",
        "DYN/runtime_class_kind/Point",
    }
    assert cached["DYN/runtime_members/Point"].cases[0]["members"] == {
        "x": {"present": True, "where": "instance"}
    }
    assert cached["DYN/runtime_class_kind/Point"].cases[0]["constructed"] is True


_TRICKY = """
import sys
import time

time.sleep({import_sleep})


def swallow():
    try:
        time.sleep(30)
    except:  # noqa: E722 - a bare except, as student code has
        return 42
    return 0


def noisy(tag):
    print("out", tag)
    print("err", tag, file=sys.stderr)
    return tag


def flood():
    while True:
        print("x" * 1000)
"""


def _tricky_root(tmp_path: Path, import_sleep: float) -> Path:
    package = tmp_path / "tricky_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source = textwrap.dedent(_TRICKY).replace("{import_sleep}", str(import_sleep))
    (package / "calc.py").write_text(source, encoding="utf-8")
    return package


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="needs an interval timer")
def test_a_swallowed_deadline_still_counts_as_a_timeout(tmp_path: Path) -> None:
    root = _tricky_root(tmp_path, 0)

    outcome = run_case_batch(
        target_root=root,
        module_path="calc",
        jobs=[_job("0", "swallow", [{}], timeout_s=0.5)],
    )

    assert outcome.jobs["0"]["status"] == "timeout"


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="needs an interval timer")
def test_import_time_counts_against_each_jobs_budget(tmp_path: Path) -> None:
    root = _tricky_root(tmp_path, 1.2)

    outcome = run_case_batch(
        target_root=root,
        module_path="calc",
        jobs=[
            _job("0", "noisy", [{"args": [1]}], timeout_s=1),
            _job("1", "noisy", [{"args": [2]}], timeout_s=5),
        ],
    )

    assert outcome.jobs["0"]["status"] == "timeout"
    assert outcome.jobs["1"]["status"] == "completed"


def test_each_job_reports_only_its_own_output(tmp_path: Path) -> None:
    root = _tricky_root(tmp_path, 0)

    outcome = run_case_batch(
        target_root=root,
        module_path="calc",
        jobs=[
            _job("0", "noisy", [{"args": ["A"]}]),
            _job("1", "noisy", [{"args": ["B"]}]),
        ],
    )

    assert "out A" in outcome.jobs["0"]["stderr"]
    assert "err A" in outcome.jobs["0"]["stderr"]
    assert "B" not in outcome.jobs["0"]["stderr"]
    assert "err B" in outcome.jobs["1"]["stderr"]


def test_observation_of_the_pattern_rules() -> None:
    def rule(**params: object) -> SimpleNamespace:
        return SimpleNamespace(rule_type="runtime_pattern", params=params)

    assert batch.observation(rule(pattern="singleton", access="instance")) == {
        "construct": False,
        "singleton": {"access": "instance"},
    }
    assert batch.observation(
        rule(pattern="observer", subscribe="on", notify="emit", notify_args=[1])
    ) == {
        "observer": {
            "subscribe": "on",
            "notify": "emit",
            "unsubscribe": None,
            "notify_args": [1],
            "subscribe_args": None,
        }
    }
    assert batch.observation(rule(pattern="delegation", spy="s")) == {"spies": True}


_PATTERNS = """
class Config:
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class Bus:
    def __init__(self):
        self.listeners = []

    def on(self, listener):
        self.listeners.append(listener)

    def off(self, listener):
        self.listeners.remove(listener)

    def emit(self, event):
        for listener in self.listeners:
            listener(event)


def price(strategy, value):
    return strategy.apply(value)
"""


def _class_job(job_id: str, qualname: str, observe: dict) -> dict:
    return {**_job(job_id, qualname, [{}], observe=observe), "kind": "class"}


def test_pattern_jobs_share_a_batch(root: Path) -> None:
    (root / "patterns.py").write_text(textwrap.dedent(_PATTERNS), encoding="utf-8")
    spy_case = {"args": [{"$spy": "strategy"}, 3]}
    observer = {
        "subscribe": "on",
        "notify": "emit",
        "unsubscribe": "off",
        "notify_args": ["placed"],
    }
    outcome = run_case_batch(
        target_root=root,
        module_path="patterns",
        jobs=[
            _class_job(
                "0",
                "Config",
                {"construct": False, "singleton": {"access": "instance"}},
            ),
            _class_job("1", "Bus", {"observer": observer}),
            _job("2", "price", [spy_case, spy_case], observe={"spies": True}),
        ],
    )

    assert outcome.status == "completed"
    singleton = outcome.jobs["0"]["cases"][0]["singleton"]
    assert singleton == {"access": "instance", "same": True, "type": "Config"}
    bus = outcome.jobs["1"]["cases"][0]
    assert bus["constructed"] is True
    assert bus["observer"] == {"notified": 1, "after_unsubscribe": 0}
    # Each case reports only its own spy calls, not those of the case before.
    assert [case["spy_calls"] for case in outcome.jobs["2"]["cases"]] == [
        [{"spy": "strategy", "member": "apply", "args": 1}]
    ] * 2


def test_prefetch_batches_pattern_rules(root: Path) -> None:
    (root / "patterns.py").write_text(textwrap.dedent(_PATTERNS), encoding="utf-8")
    ctx, rules = _ctx(root, "patterns", ["Config", "Bus"], "runtime_pattern")
    for entity in [*ctx.source_by_id.values(), *ctx.target_by_id.values()]:
        entity.kind = "class"
    rules[0].params = {"cases": [{}], "pattern": "singleton", "access": "instance"}
    rules[1].params = {
        "cases": [{}],
        "pattern": "observer",
        "subscribe": "on",
        "notify": "emit",
        "notify_args": ["x"],
    }

    batch.prefetch(rules, ctx)

    cached = {key[0]: outcome for key, outcome in ctx.dynamic_cache.items()}
    singleton = cached["DYN/runtime_pattern/Config"].cases[0]["singleton"]
    assert singleton["same"] is True
    observer = cached["DYN/runtime_pattern/Bus"].cases[0]["observer"]
    assert observer == {"notified": 1}


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="needs an interval timer")
def test_a_job_that_floods_its_output_times_out_alone(tmp_path: Path) -> None:
    """A job printing in an endless loop keeps only the tail of its output:
    it ends as its own timeout, under the memory limit, and the other jobs
    of the batch keep their results (audit E4)."""
    from pythonarchtesting.dynamic.sandbox import SandboxPolicy

    root = _tricky_root(tmp_path, 0)

    outcome = run_case_batch(
        target_root=root,
        module_path="calc",
        sandbox=SandboxPolicy(mode="limits"),
        jobs=[
            _job("0", "noisy", [{"args": ["A"]}]),
            _job("1", "flood", [{}], timeout_s=3),
            _job("2", "noisy", [{"args": ["B"]}]),
        ],
    )

    assert outcome.status == "completed", outcome.error
    assert outcome.jobs["1"]["status"] == "timeout"
    flooded = outcome.jobs["1"]["stderr"]
    assert 0 < len(flooded) <= 2000 and set(flooded) <= {"x", "\n"}
    assert outcome.jobs["0"]["status"] == outcome.jobs["2"]["status"] == "completed"
    assert "err B" in outcome.jobs["2"]["stderr"]
