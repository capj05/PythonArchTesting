"""In-process tests for the probe's helpers.

The probe normally runs in a child interpreter, where coverage is not measured
and failures are only visible through the JSON response. These tests call its
helpers directly. They never call ``ImportRecorder.install`` or ``main``,
which patch interpreter-wide state.
"""

from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.dynamic import probe


class _Frame:
    def __init__(self, filename: str | None, lineno: int = 7) -> None:
        self.f_globals: dict[str, Any] = {"__file__": filename} if filename else {}
        self.f_lineno = lineno


def test_import_recorder_attributes_and_filters_by_root(tmp_path: Path) -> None:
    recorder = probe.ImportRecorder(str(tmp_path))
    inside = str(tmp_path / "pkg" / "mod.py")

    recorder._note("json", _Frame(inside, 3), None, 0, ())
    recorder._note("re", _Frame("/usr/lib/python3/json/decoder.py"), None, 0, ())
    recorder._note("", _Frame(inside, 4), "pkg", 1, ("helpers", "*"))
    recorder.phase = "case 0"
    recorder._note("sqlite3", _Frame(inside, 9), None, 0, ())
    recorder._note("sqlite3", _Frame(inside, 9), None, 0, ())
    recorder._note("x", _Frame(None), None, 0, ())

    assert [event["module"] for event in recorder.events] == [
        "json",
        "pkg.helpers",
        "sqlite3",
        "sqlite3",
    ]
    hits = recorder.forbidden_hits(["sqlite3", "pkg"], ["pkg.helpers"], {"case 0"})
    assert [(hit["module"], hit["line"]) for hit in hits] == [("sqlite3", 9)]
    assert hits[0]["file"] == "pkg/mod.py"


def _module(
    source: str,
    name: str = "target_mod",
    filename: str = "target_mod.py",
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = filename
    if monkeypatch is not None:
        monkeypatch.setitem(sys.modules, name, module)
    exec(compile(source, filename, "exec"), module.__dict__)  # nosec B102
    return module


_OTHER = """
def helper(x):
    return x + 1


class Store:
    def put(self, key):
        return key
"""

_CALLER = """
import collections
import json
import pickle

import other_mod


def _local(x):
    return other_mod.helper(x)


def work(store):
    for _ in range(3):
        store.put("k")
    _local(1)
    len([1])
    sorted([2, 1])
    try:
        open("/nonexistent-dir/file.txt")
    except OSError:
        pass
    json.dumps([1])
    pickle.dumps(1)
    collections.deque().append(1)
    return 0
"""


def test_call_recorder_attributes_calls_to_the_callee_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other = _module(_OTHER, "other_mod", "other_mod.py", monkeypatch)
    caller = _module(_CALLER, "caller_mod", "caller_mod.py", monkeypatch)
    recorder = probe.CallRecorder("caller_mod", None)

    before = sys.getprofile()
    with recorder.watching():
        caller.work(other.Store())

    assert sys.getprofile() is before
    # The loop calls Store.put three times from one line: reported once. The
    # same-module helper is reported as a local call and followed to its own
    # outward call; builtins are not a layer, except open(), which is io's;
    # C functions and C methods are attributed to their modules.
    assert [
        (c["module"], c["callee"], c["caller"], bool(c.get("local")))
        for c in recorder.calls
    ] == [
        ("other_mod", "Store.put", "work", False),
        ("caller_mod", "_local", "work", True),
        ("other_mod", "helper", "_local", False),
        ("io", "open", "work", False),
        ("json", "dumps", "work", False),
        ("pickle", "dumps", "work", False),
        ("collections", "deque.append", "work", False),
    ]


_THING = """
class Thing:
    def __init__(self):
        self._size = 0

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        self._size = value
"""

_RESIZER = """
def resize(thing):
    thing.size = 3
"""


def test_call_recorder_sees_through_the_write_recorder_wrapper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    things = _module(_THING, "thing_mod", str(tmp_path / "thing_mod.py"), monkeypatch)
    resizer = _module(
        _RESIZER, "resizer_mod", str(tmp_path / "resizer_mod.py"), monkeypatch
    )
    writes = probe.WriteRecorder(str(tmp_path))
    writes.install()
    calls = probe.CallRecorder("resizer_mod", None)
    thing = things.Thing()

    writes.start()
    with calls.watching():
        resizer.resize(thing)
    writes.active = False

    # The wrapped __setattr__ is the probe's code, not a call into a layer;
    # the property setter it dispatches to is attributed to the assigning code.
    assert [(c["module"], c["callee"], c["caller"]) for c in calls.calls] == [
        ("thing_mod", "Thing.size", "resize")
    ]
    # Assigning through a property setter is the class's own code at work.
    assert writes.writes == []


def test_local_module_strips_only_the_probe_package_prefix() -> None:
    assert probe._local_module("pkg.repo", "pkg") == "repo"
    assert probe._local_module("pkgx.repo", "pkg") == "pkgx.repo"
    assert probe._local_module("repo", None) == "repo"
    assert probe._local_module(None, "pkg") is None


_MODEL = """
import enum


class Base:
    def set_owner(self, owner):
        self.owner = owner


class Account(Base):
    def __init__(self):
        self.balance = 0


class Problem(Exception):
    pass


class Colour(enum.Enum):
    RED = 1


def poke(account):
    account.balance = 5
"""


def test_write_recorder_wraps_target_classes_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = _module(_MODEL, "model_mod", str(tmp_path / "model_mod.py"), monkeypatch)
    recorder = probe.WriteRecorder(str(tmp_path))

    recorder.install()
    wrapped = model.Base.__setattr__
    recorder.install()

    assert getattr(wrapped, probe.WriteRecorder._MARK)
    assert model.Base.__setattr__ is wrapped
    # The subclass inherits the base's wrapper rather than getting its own.
    assert "__setattr__" not in vars(model.Account)
    assert "__setattr__" not in vars(model.Problem)
    assert "__setattr__" not in vars(model.Colour)


def test_write_recorder_records_only_while_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = _module(_MODEL, "model_mod", str(tmp_path / "model_mod.py"), monkeypatch)
    recorder = probe.WriteRecorder(str(tmp_path))
    recorder.install()
    account = model.Account()

    model.poke(account)
    assert recorder.writes == []

    recorder.start()
    model.poke(account)
    model.poke(account)
    account.set_owner("ada")
    account.note = "set from this test file, outside the target root"
    recorder.active = False

    assert recorder.writes == [
        {
            "class": "Account",
            "attribute": "balance",
            "writer": "model_mod:poke",
            "file": "model_mod.py",
            "line": _MODEL.splitlines().index("    account.balance = 5") + 1,
            "change": "assigned",
        }
    ]

    recorder.start()
    assert recorder.writes == []


_SOURCE = """
import json


class Counter:
    def __init__(self, start=0):
        self.value = start

    def bump(self, by):
        if by < 0:
            raise ValueError("negative")
        self.value += by
        return json.dumps(self.value)

    @staticmethod
    def zero():
        return json.dumps(0)


def pair(a, b=2):
    return Pair(a, b)


class Pair:
    def __init__(self, a, b):
        self.a = a
        self.b = b


def poke(counter):
    counter.value = 99
"""


def _run(
    qualname: str,
    kind: str,
    case: dict[str, Any],
    *,
    tmp_path: Path | None = None,
    monkeypatch: pytest.MonkeyPatch | None = None,
    **extra: Any,
) -> dict:
    request = {
        "qualname": qualname,
        "kind": kind,
        "init": extra.get("init"),
        "observe": extra.get("observe", {"calls": True}),
    }
    root = tmp_path or Path("/nonexistent-root")
    module = _module(_SOURCE, "target_mod", str(root / "target_mod.py"), monkeypatch)
    writes = probe.WriteRecorder(str(root))
    return probe._run_case(0, case, request, module, None, writes)


def test_run_case_method_reports_calls() -> None:
    outcome = _run("Counter.bump", "method", {"args": [2]}, init={"args": [1]})

    assert outcome["status"] == "passed", outcome["failures"]
    assert [call["module"] for call in outcome["calls"]] == ["json"]
    assert "writes" not in outcome


def test_run_case_reports_a_raise_without_failing() -> None:
    outcome = _run("Counter.bump", "method", {"args": [-1]})

    assert outcome["status"] == "passed"
    assert outcome["raised"] == "ValueError: negative"
    assert outcome["calls"] == []


def test_run_case_a_raise_fails_a_flow_capture() -> None:
    outcome = _run(
        "Counter.bump", "method", {"args": [-1], "capture_stages": {"spans": []}}
    )

    assert outcome["status"] == "failed"
    assert outcome["failures"] == ["unexpected ValueError: negative"]
    assert "Traceback" in outcome["traceback"]
    assert outcome["stages"] == []
    assert "flow_calls" not in outcome


def test_run_case_a_raise_does_not_fail_a_flow_call_trace() -> None:
    outcome = _run("Counter.bump", "method", {"args": [-1], "flow_calls": True})

    assert outcome["status"] == "passed"
    assert outcome["raised"] == "ValueError: negative"
    assert outcome["flow_calls"] == []
    assert "stages" not in outcome


def test_run_case_static_method_needs_no_instance() -> None:
    outcome = _run("Counter.zero", "method", {}, init={"args": [1, 2, 3]})

    assert outcome["status"] == "passed"
    assert [call["module"] for call in outcome["calls"]] == ["json"]


def test_run_case_reports_foreign_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outcome = _run(
        "poke",
        "function",
        {"args": [{"$new": "Counter"}]},
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        observe={"writes": True},
    )

    assert [(w["class"], w["attribute"]) for w in outcome["writes"]] == [
        ("Counter", "value")
    ]
    assert "calls" not in outcome


def test_run_case_setup_errors() -> None:
    bad_ctor = _run("Counter.bump", "method", {"args": [1]}, init={"args": [1, 2, 3]})
    bad_new = _run("pair", "function", {"args": [{"$new": "Pair", "args": [1]}]})
    bad_name = _run("pair", "function", {"args": [{"$new": "Pair.nope"}]})
    no_package = _run("pair", "function", {"args": [{"$new": "Nowhere"}]})

    assert bad_ctor["status"] == "error"
    assert "constructing 'Counter' raised TypeError" in bad_ctor["failures"][0]
    assert "constructing 'Pair' raised TypeError" in bad_new["failures"][0]
    assert "no attribute 'nope'" in bad_name["failures"][0]
    assert "cannot resolve 'Nowhere' in the target module" in no_package["failures"][0]


def test_importing_package_falls_back_to_the_spec_parent() -> None:
    spec = types.SimpleNamespace(parent="pkg.sub")

    assert probe._importing_package({"__package__": "pkg"}) == "pkg"
    assert probe._importing_package({"__spec__": spec}) == "pkg.sub"
    assert probe._importing_package(None) is None


_FLOW = """
import json
import sys


def parse(text):
    return text.strip()


def check(text):
    return helper(text)


def helper(text):
    return len(text) > 0


def store(text, sink):
    sink.append(text)


def pipeline(text, sink):
    text = text + ""
    text = parse(text)
    if check(text):
        store(json.dumps(text), sink)
    return text


def each(items, sink):
    for item in items:
        store(parse(item), sink)
    return sink


def mixed(text):
    json.dumps(text.upper())
    return (lambda t: parse(t))(text)


def explode(text):
    parse(text)
    raise ValueError("boom")


def counter():
    yield parse("a")


def untraceable():
    sys.settrace(None)
    return parse("a")
"""


def _flow_module(tmp_path: Path) -> tuple[types.ModuleType, probe._Project]:
    module = _module(_FLOW, "flow_mod", str(tmp_path / "flow_mod.py"))
    return module, probe._Project(str(tmp_path), None)


def _span(stage: str, first: str, last: str | None = None) -> dict[str, Any]:
    lines = _FLOW.splitlines()
    start = next(no for no, line in enumerate(lines, 1) if first in line)
    end = next(no for no, line in enumerate(lines, 1) if (last or first) in line)
    return {"stage": stage, "start": start, "end": end, "variable": "text"}


def _named(*qualnames: str) -> list[dict[str, str]]:
    return [{"module": "flow_mod", "qualname": name} for name in qualnames]


def test_stages_record_the_project_functions_called_directly(tmp_path: Path) -> None:
    module, project = _flow_module(tmp_path)
    # "checked" labels the whole "if" block, which contains "stored".
    spans = [
        _span("received", 'text = text + ""'),
        _span("parsed", "text = parse(text)"),
        _span("checked", "if check(text):", "store(json.dumps(text), sink)"),
        _span("stored", "store(json.dumps(text), sink)"),
    ]
    stages: list[list[Any]] = []

    result = probe._call_with_trace(
        module.pipeline, [" a ", []], {}, project, spans, stages
    )

    assert result == "a"
    # "received" calls nothing of the project; check's own call of helper is
    # not direct; json.dumps is not project code; the inner span finishes
    # first.
    assert stages == [
        ["received", []],
        ["parsed", _named("parse")],
        ["stored", _named("store")],
        ["checked", _named("check")],
    ]


def test_a_stage_in_a_loop_is_recorded_per_iteration(tmp_path: Path) -> None:
    module, project = _flow_module(tmp_path)
    spans = [_span("each", "store(parse(item), sink)")]
    stages: list[list[Any]] = []

    probe._call_with_trace(module.each, [["a", "b"], []], {}, project, spans, stages)

    assert stages == [
        ["each", _named("parse", "store")],
        ["each", _named("parse", "store")],
    ]


def test_target_calls_are_recorded_in_order_at_any_depth(tmp_path: Path) -> None:
    module, project = _flow_module(tmp_path)
    calls: list[dict[str, str]] = []

    probe._call_with_trace(module.pipeline, [" a ", []], {}, project, calls=calls)

    assert calls == _named("parse", "check", "helper", "store")


def test_standard_library_builtins_and_lambdas_are_not_recorded(
    tmp_path: Path,
) -> None:
    module, project = _flow_module(tmp_path)
    calls: list[dict[str, str]] = []

    probe._call_with_trace(module.mixed, ["a"], {}, project, calls=calls)

    # The lambda itself is "<lambda>" code; what it calls still counts.
    assert calls == _named("parse")


def test_target_calls_are_capped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, project = _flow_module(tmp_path)
    monkeypatch.setattr(probe, "_FLOW_CALL_LIMIT", 2)
    calls: list[dict[str, str]] = []

    probe._call_with_trace(module.pipeline, [" a ", []], {}, project, calls=calls)

    assert calls == _named("parse", "check")


def test_a_raise_keeps_the_calls_and_restores_the_tracer(tmp_path: Path) -> None:
    module, project = _flow_module(tmp_path)
    calls: list[dict[str, str]] = []
    before = sys.gettrace()

    with pytest.raises(ValueError, match="boom"):
        probe._call_with_trace(module.explode, ["a"], {}, project, calls=calls)

    assert calls == _named("parse")
    assert sys.gettrace() is before


def test_the_tracer_is_restored_after_a_normal_call(tmp_path: Path) -> None:
    module, project = _flow_module(tmp_path)
    before = sys.gettrace()

    probe._call_with_trace(module.pipeline, ["a", []], {}, project, calls=[])

    assert sys.gettrace() is before


@pytest.mark.parametrize(
    ("name", "fragment"),
    [
        ("counter", "generators or coroutines"),
        ("untraceable", "replaced the trace function"),
    ],
)
def test_untraceable_targets_are_setup_errors(
    tmp_path: Path, name: str, fragment: str
) -> None:
    module, project = _flow_module(tmp_path)
    before = sys.gettrace()

    with pytest.raises(probe.CaseSetupError, match=fragment):
        probe._call_with_trace(getattr(module, name), [], {}, project, calls=[])

    assert sys.gettrace() is before


def test_tracing_a_builtin_is_a_setup_error(tmp_path: Path) -> None:
    with pytest.raises(probe.CaseSetupError, match="not a builtin"):
        probe._call_with_trace(len, [[1]], {}, probe._Project(str(tmp_path), None))


def _flow_case(tmp_path: Path, qualname: str, case: dict[str, Any]) -> dict:
    module, _ = _flow_module(tmp_path)
    request = {
        "qualname": qualname,
        "kind": "function",
        "observe": {},
        "target_root": str(tmp_path),
    }
    return probe._run_case(0, case, request, module, None)


def test_run_case_reports_reference_stages_and_target_calls(tmp_path: Path) -> None:
    spans = [_span("parsed", "text = parse(text)")]
    reference = _flow_case(
        tmp_path,
        "pipeline",
        {"args": ["a", []], "capture_stages": {"spans": spans}},
    )
    target = _flow_case(tmp_path, "pipeline", {"args": ["a", []], "flow_calls": True})

    assert reference["status"] == "passed", reference["failures"]
    assert reference["stages"] == [["parsed", _named("parse")]]
    assert "lines" not in reference
    assert target["flow_calls"] == _named("parse", "check", "helper", "store")


def test_run_case_reports_a_generator_as_a_setup_error(tmp_path: Path) -> None:
    outcome = _flow_case(tmp_path, "counter", {"flow_calls": True})

    assert outcome["status"] == "error"
    assert "generators or coroutines" in outcome["failures"][0]


def test_run_case_reports_the_lines_no_case_ran(tmp_path: Path) -> None:
    module = _module(_SOURCE, filename=str(tmp_path / "target_mod.py"))
    request = {
        "qualname": "Counter.bump",
        "kind": "method",
        "observe": {},
        "target_root": str(tmp_path),
    }
    before = sys.gettrace()

    outcome = probe._run_case(0, {"args": [2], "init": {}}, request, module, None)

    raise_line = _SOURCE.splitlines().index('            raise ValueError("negative")')
    assert outcome["lines"]["file"] == "target_mod.py"
    assert outcome["lines"]["missed"] == [raise_line + 1]
    assert raise_line + 2 in outcome["lines"]["run"]
    assert sys.gettrace() is before


def test_run_case_reports_no_lines_without_a_target_root() -> None:
    outcome = _run("Counter.bump", "method", {"args": [2]})

    assert "lines" not in outcome


_THREADED = """
import json
import threading


def spawn():
    worker = threading.Thread(target=lambda: json.dumps(1))
    worker.start()
"""


def test_run_case_follows_threads_the_target_starts(tmp_path: Path) -> None:
    module = _module(_THREADED, filename=str(tmp_path / "target_mod.py"))
    request = {
        "qualname": "spawn",
        "kind": "function",
        "observe": {"calls": True},
        "target_root": str(tmp_path),
    }
    before = threading.getprofile()

    outcome = probe._run_case(0, {}, request, module, None)

    assert ("json", "dumps") in {
        (call["module"], call["callee"]) for call in outcome["calls"]
    }
    assert outcome["lines"]["missed"] == []
    assert threading.getprofile() is before


def test_joining_new_threads_gives_up_after_the_grace_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(probe, "_THREAD_GRACE_S", 0.05)
    release = threading.Event()
    worker = threading.Thread(target=release.wait)

    with probe._joining_new_threads():
        worker.start()

    assert worker.is_alive()
    release.set()
    worker.join()


def _forget(*prefixes: str) -> None:
    for name in list(sys.modules):
        if name.split(".")[0] in prefixes:
            del sys.modules[name]


def test_sibling_names_never_shadow_another_module(tmp_path: Path) -> None:
    package = tmp_path / "zz_student"
    (package / "zz_domain").mkdir(parents=True)
    (package / "zz_domain" / "model.py").write_text("", encoding="utf-8")
    (package / "__pycache__").mkdir()
    for name in (
        "__init__",
        "zz_inventory",
        "json",
        "calendar",
        "pytest",
        "zz_student",
    ):
        (package / f"{name}.py").write_text("", encoding="utf-8")
    (package / "not-a-name.py").write_text("", encoding="utf-8")

    names = probe._sibling_names(str(package), "zz_student")

    # json and calendar: the standard library's; pytest: installed.
    assert names == {"zz_domain", "zz_inventory"}


def test_sibling_aliases_bind_one_module_under_both_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A package without ``__init__.py`` whose modules import each other
    absolutely: one module object, so the classes are the same."""
    import importlib

    package = tmp_path / "zz_student"
    (package / "zz_domain").mkdir(parents=True)
    (package / "zz_domain" / "model.py").write_text(
        "class Item:\n    pass\n", encoding="utf-8"
    )
    (package / "zz_inventory.py").write_text(
        "from zz_domain.model import Item\n\nclass Inventory:\n    pass\n",
        encoding="utf-8",
    )
    (package / "zz_shop.py").write_text(
        "import zz_inventory\nfrom zz_inventory import Inventory\n", encoding="utf-8"
    )
    names = probe._sibling_names(str(package), "zz_student")
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])
    monkeypatch.setattr(
        sys, "meta_path", [probe._SiblingAliases("zz_student", names), *sys.meta_path]
    )
    try:
        probe._stand_in_package(str(package), "zz_student")
        shop = importlib.import_module("zz_student.zz_shop")
        inventory = importlib.import_module("zz_student.zz_inventory")
        model = importlib.import_module("zz_student.zz_domain.model")

        assert shop.Inventory is inventory.Inventory
        assert shop.zz_inventory is inventory
        assert sys.modules["zz_inventory"] is inventory
        assert inventory.Item is model.Item
        assert sys.modules["zz_domain.model"] is model
        # Each module keeps its own spec, not the alias's.
        assert inventory.__spec__.name == "zz_student.zz_inventory"
        assert sys.modules["zz_student"].__path__ == [str(package)]
    finally:
        _forget("zz_student", "zz_inventory", "zz_shop", "zz_domain")


def test_an_unresolvable_new_names_what_the_case_references() -> None:
    """The case's ``$new`` names a class the submission lacks: the setup
    error says which, so the result can name the missing entity."""
    with pytest.raises(probe.CaseSetupError) as raised:
        probe._build_value({"$new": "zz_nowhere.Inventory", "args": []}, {}, None)

    assert raised.value.unresolved == "zz_nowhere.Inventory"


def test_a_setup_error_of_another_kind_names_nothing() -> None:
    assert probe.CaseSetupError("steps need an instance").unresolved is None


def test_the_imports_fallback_leaves_no_second_module_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``mode="imports"`` first loads the module without its package's
    ``__init__.py``; a module that needs the package's names falls back to a
    plain import. A sibling the first attempt aliased (``import
    zz_inventory``) must not survive into the second as another module."""
    import importlib

    package = tmp_path / "zz_student"
    package.mkdir()
    (package / "__init__.py").write_text("VERSION = 1\n", encoding="utf-8")
    (package / "zz_inventory.py").write_text(
        "class Inventory:\n    pass\n", encoding="utf-8"
    )
    (package / "zz_shop.py").write_text(
        "import zz_inventory\nfrom . import VERSION\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sys, "meta_path", list(sys.meta_path))
    try:
        shop, _ = probe._import_target(
            {
                "target_root": str(package),
                "package": "zz_student",
                "module_path": "zz_shop",
                "mode": "imports",
            }
        )
        inventory = importlib.import_module("zz_student.zz_inventory")

        assert shop.zz_inventory is inventory
        assert sys.modules["zz_inventory"] is inventory
    finally:
        _forget("zz_student", "zz_inventory", "zz_shop")


_WORLD = """
class Sack:
    def __init__(self):
        self.things = []

    def add(self, thing):
        self.things.append(thing)


class Room:
    def __init__(self):
        self.things = []


SACK = Sack()
ROOMS = {"hall": Room()}
here = ROOMS["hall"]
"""

_ACTIONS = """
import world_mod


def take(word):
    world_mod.SACK.add(word)
    world_mod.SACK.things.append(word)
    world_mod.here.things.append(word)


def stuff(sack):
    sack.things.append(1)
"""


def test_write_recorder_watches_objects_module_globals_hold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = _module(_WORLD, "world_mod", str(tmp_path / "world_mod.py"), monkeypatch)
    actions = _module(
        _ACTIONS, "actions_mod", str(tmp_path / "actions_mod.py"), monkeypatch
    )
    recorder = probe.WriteRecorder(str(tmp_path))

    # No argument holds the sack or the room: the module globals do. The
    # method's own change is no foreign write; a global holding the object
    # itself names it before a dict that holds it too.
    recorder.start(["lamp"])
    with recorder.watching():
        actions.take("lamp")
    recorder.active = False

    assert [
        (w["class"], w["attribute"], w["change"], w.get("held_by"))
        for w in recorder.writes
    ] == [
        ("Sack", "things", "mutated", "world_mod.SACK"),
        ("Room", "things", "mutated", "world_mod.here"),
    ]

    # An object the case passes is an argument's, even when a global holds it.
    recorder.start([world.SACK])
    with recorder.watching():
        actions.stuff(world.SACK)
    recorder.active = False

    assert [(w["class"], w.get("held_by")) for w in recorder.writes] == [("Sack", None)]
