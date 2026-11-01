"""In-process tests for the probe's module-edge and instantiation recording.

Like ``test_dynamic_probe_inprocess``, these build throwaway modules under
``tmp_path`` and call the probe's recorders directly; the wrappers they install
only ever touch classes of those modules.
"""

from __future__ import annotations

import io
import sys
import textwrap
import types
from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.dynamic import probe

_PACKAGE = "edge_pkg"


def _module(
    root: Path, name: str, source: str, monkeypatch: pytest.MonkeyPatch
) -> types.ModuleType:
    """Build ``edge_pkg.<name>`` (or the package itself) from ``source``."""
    dotted = f"{_PACKAGE}.{name}" if name else _PACKAGE
    filename = root / (f"{name}.py" if name else "__init__.py")
    module = types.ModuleType(dotted)
    module.__file__ = str(filename)
    monkeypatch.setitem(sys.modules, dotted, module)
    exec(  # nosec B102
        compile(textwrap.dedent(source), str(filename), "exec"), module.__dict__
    )
    return module


_REPO = """
class Store:
    def put(self, key):
        return key
"""

_SERVICE = """
import json


def _helper(store, key):
    return store.put(key)


def run(store, key):
    len([key])
    json.dumps([key])
    return _helper(store, key)
"""

_CONTROLLER = """
def handle(store, key):
    return [service.run(store, item) for item in (key, key)]
"""

_INIT = """
def entry(store):
    return controller.handle(store, "k")
"""


def _edge_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, types.ModuleType]:
    modules = {
        "repo": _module(tmp_path, "repo", _REPO, monkeypatch),
        "service": _module(tmp_path, "service", _SERVICE, monkeypatch),
        "controller": _module(tmp_path, "controller", _CONTROLLER, monkeypatch),
        "": _module(tmp_path, "", _INIT, monkeypatch),
    }
    modules["controller"].service = modules["service"]  # type: ignore[attr-defined]
    modules[""].controller = modules["controller"]  # type: ignore[attr-defined]
    return modules


def test_edges_mode_records_only_calls_between_project_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    modules = _edge_project(tmp_path, monkeypatch)
    project = probe._Project(str(tmp_path), _PACKAGE)
    recorder = probe.CallRecorder(None, _PACKAGE, project)

    with recorder.watching():
        modules[""].entry(modules["repo"].Store())

    # The call from this test file into the package is not an edge; the
    # comprehension, json and len() are not either. The same-module helper is
    # reported as a local call (two entities of one module may still belong
    # to different layers). The package itself is named "__init__".
    assert [
        (c["from"], c["module"], c["callee"], bool(c.get("local")))
        for c in recorder.calls
    ] == [
        ("__init__", "controller", "handle", False),
        ("controller", "service", "run", False),
        ("service", "service", "_helper", True),
        ("service", "repo", "Store.put", False),
    ]


def test_project_relpath_is_relative_and_none_outside(tmp_path: Path) -> None:
    project = probe._Project(str(tmp_path), None)

    assert project.relpath(str(tmp_path / "a" / "b.py")) == "a/b.py"
    assert project.relpath(str(tmp_path / "a" / "b.py")) == "a/b.py"  # cached
    assert project.relpath("/elsewhere/b.py") is None
    assert project.relpath(None) is None


@pytest.mark.parametrize(
    "filename", ["<frozen posixpath>", "<string>", "pkg/mod.py", "mod.py"]
)
def test_project_relpath_rejects_pseudo_and_relative_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str
) -> None:
    # The probe runs with the target root as its working directory, where a
    # relative or pseudo name would otherwise resolve inside the project.
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    project = probe._Project(str(tmp_path), None)

    assert project.relpath(filename) is None


def test_local_module_names_the_package_itself_init() -> None:
    assert probe._local_module("pkg", "pkg") == "__init__"
    assert probe._local_module("pkg.sub", "pkg") == "sub"


def test_run_case_in_edges_mode_needs_the_target_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    modules = _edge_project(tmp_path, monkeypatch)
    request = {
        "qualname": "handle",
        "kind": "function",
        "observe": {"calls": "edges"},
        "target_root": str(tmp_path),
    }

    outcome = probe._run_case(
        0,
        {"args": [{"$new": "repo.Store"}, "k"]},
        request,
        modules["controller"],
        _PACKAGE,
    )

    assert outcome["status"] == "passed", outcome["failures"]
    assert [
        (c["from"], c["module"]) for c in outcome["calls"] if not c.get("local")
    ] == [
        ("controller", "service"),
        ("service", "repo"),
    ]


_MODEL = """
import dataclasses


class Repo:
    def __init__(self, name="db"):
        self.name = name


class Base:
    def __init__(self, size):
        self.size = size


class Derived(Base):
    def __init__(self, size):
        super().__init__(size)


class Leaf(Derived):
    pass


@dataclasses.dataclass
class Point:
    x: int
    y: int


class Token:
    def __new__(cls, value):
        obj = super().__new__(cls)
        obj.value = value
        return obj
"""

_SERVICE_MODEL = """
class Service:
    def __init__(self, repo=None):
        self.repo = repo or model.Repo()

    def run(self, size):
        return model.Derived(size), model.Leaf(size)

    def other(self):
        return model.Point(1, 2), model.Token("t")


def build():
    return model.Repo("x")
"""


def _instance_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[types.ModuleType, types.ModuleType]:
    model = _module(tmp_path, "model", _MODEL, monkeypatch)
    service = _module(tmp_path, "service", _SERVICE_MODEL, monkeypatch)
    service.model = model  # type: ignore[attr-defined]
    return model, service


def _created(outcome: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(i["module"], i["class"], i["creator"]) for i in outcome["instances"]]


def _run_instances(
    module: types.ModuleType,
    qualname: str,
    case: dict[str, Any],
    recorder: probe.InstanceRecorder,
    *,
    kind: str = "method",
    init: Any = None,
) -> dict[str, Any]:
    request = {
        "qualname": qualname,
        "kind": kind,
        "init": init,
        "observe": {"instances": True},
    }
    return probe._run_case(0, case, request, module, _PACKAGE, None, recorder)


def test_construction_while_the_method_instance_is_built_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, service = _instance_project(tmp_path, monkeypatch)
    recorder = probe.InstanceRecorder(str(tmp_path), _PACKAGE)

    outcome = _run_instances(service, "Service.run", {"args": [3]}, recorder)

    assert outcome["status"] == "passed", outcome["failures"]
    # The probe builds the Service itself, which is not counted; the Repo
    # Service.__init__ creates is. A super().__init__ chain is one Derived.
    assert _created(outcome) == [
        ("model", "Repo", "service:Service.__init__"),
        ("model", "Derived", "service:Service.run"),
        ("model", "Leaf", "service:Service.run"),
    ]
    assert outcome["instances"][0]["from"] == "service"
    assert outcome["instances"][0]["file"] == "service.py"
    assert recorder.active is False


def test_dataclasses_and_classes_with_only_new_are_recorded_and_still_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, service = _instance_project(tmp_path, monkeypatch)
    recorder = probe.InstanceRecorder(str(tmp_path), _PACKAGE)

    outcome = _run_instances(service, "Service.other", {}, recorder)

    assert "raised" not in outcome
    assert [(i["class"], i["from"]) for i in outcome["instances"]][1:] == [
        ("Point", "service"),
        ("Token", "service"),
    ]
    # The wrapper passes no arguments on to object.__init__.
    assert model.Token("v").value == "v"
    assert model.Point(1, 2) == model.Point(1, 2)


def test_objects_the_probe_builds_for_arguments_are_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, service = _instance_project(tmp_path, monkeypatch)
    recorder = probe.InstanceRecorder(str(tmp_path), _PACKAGE)

    outcome = _run_instances(
        service,
        "Service.run",
        {"args": [1]},
        recorder,
        init={"args": [{"$new": "model.Repo"}]},
    )

    assert [i["class"] for i in outcome["instances"]] == ["Derived", "Leaf"]


def test_instances_are_reset_between_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, service = _instance_project(tmp_path, monkeypatch)
    recorder = probe.InstanceRecorder(str(tmp_path), _PACKAGE)

    first = _run_instances(service, "build", {}, recorder, kind="function")
    model.Repo()  # outside a case: not recorded
    second = _run_instances(service, "build", {}, recorder, kind="function")

    assert _created(first) == [("model", "Repo", "service:build")]
    assert second["instances"] == first["instances"]
    assert recorder.instances == first["instances"]


def test_a_setup_error_stops_recording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, service = _instance_project(tmp_path, monkeypatch)
    recorder = probe.InstanceRecorder(str(tmp_path), _PACKAGE)

    outcome = _run_instances(
        service, "Service.run", {}, recorder, init={"args": [1, 2, 3]}
    )

    assert outcome["status"] == "error"
    assert recorder.active is False
    assert "instances" not in outcome


def test_classes_are_wrapped_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, _ = _instance_project(tmp_path, monkeypatch)
    recorder = probe.InstanceRecorder(str(tmp_path), _PACKAGE)

    recorder.start()
    wrapped = model.Base.__init__
    recorder.start()
    recorder.active = False

    assert getattr(wrapped, probe.InstanceRecorder._MARK)
    assert model.Base.__init__ is wrapped
    # A subclass without its own __init__ inherits the base's wrapper.
    assert "__init__" not in vars(model.Leaf)


def test_codes_of_follows_wrapped_and_stops_on_a_loop() -> None:
    def inner() -> None:
        return None

    def outer() -> None:
        return None

    outer.__wrapped__ = inner  # type: ignore[attr-defined]
    looped = types.SimpleNamespace()
    looped.__wrapped__ = looped

    assert probe._codes_of(outer) == [outer.__code__, inner.__code__]
    assert probe._codes_of(looped) == []
    assert probe._codes_of(None) == []


def test_the_call_recorder_attributes_a_constructor_through_the_wrapper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, service = _instance_project(tmp_path, monkeypatch)
    instances = probe.InstanceRecorder(str(tmp_path), _PACKAGE)
    instances.start()
    instances.active = False
    calls = probe.CallRecorder(f"{_PACKAGE}.service", _PACKAGE)

    with calls.watching():
        service.build()

    assert [(c["module"], c["callee"], c["caller"]) for c in calls.calls] == [
        ("model", "Repo.__init__", "build")
    ]


# No importlib.import_module here: in a real probe run ImportRecorder hooks
# it, so the call is made from the probe's own frame and is no library use of
# the project (the module it loads is seen when the project calls into it).
_TECH_SERVICE = """
import json
import pickle


def run(store, key):
    len([key])
    [key].append(key)
    json.dumps([key])
    pickle.dumps(key)
    return store.put(key)
"""


def _tech_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, types.ModuleType]:
    return {
        "repo": _module(tmp_path, "repo", _REPO, monkeypatch),
        "service": _module(tmp_path, "service", _TECH_SERVICE, monkeypatch),
    }


def test_edges_with_external_record_calls_from_project_code_outward(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    modules = _tech_project(tmp_path, monkeypatch)
    project = probe._Project(str(tmp_path), _PACKAGE)
    recorder = probe.CallRecorder(None, _PACKAGE, project, external=True)

    with recorder.watching():
        modules["service"].run(modules["repo"].Store(), "k")

    external = [(c["from"], c["module"]) for c in recorder.calls if c.get("external")]
    internal = [
        (c["from"], c["module"]) for c in recorder.calls if not c.get("external")
    ]
    # Only the boundary is recorded: json's own calls into json.encoder are
    # not; pickle.dumps is _pickle.dumps underneath; builtins are no module.
    assert external == [("service", "json"), ("service", "pickle")]
    assert internal == [("service", "repo")]


def test_edges_without_external_stay_internal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    modules = _tech_project(tmp_path, monkeypatch)
    project = probe._Project(str(tmp_path), _PACKAGE)
    recorder = probe.CallRecorder(None, _PACKAGE, project)

    with recorder.watching():
        modules["service"].run(modules["repo"].Store(), "k")

    assert [(c["from"], c["module"]) for c in recorder.calls] == [("service", "repo")]


def test_run_case_passes_observe_external_to_the_recorder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    modules = _tech_project(tmp_path, monkeypatch)
    request = {
        "qualname": "run",
        "kind": "function",
        "observe": {"calls": "edges", "external": True},
        "target_root": str(tmp_path),
    }

    outcome = probe._run_case(
        0,
        {"args": [{"$new": "repo.Store"}, "k"]},
        request,
        modules["service"],
        _PACKAGE,
    )

    assert outcome["status"] == "passed", outcome["failures"]
    assert {c["module"] for c in outcome["calls"] if c.get("external")} == {
        "json",
        "pickle",
    }


def test_classes_loaded_after_start_are_wrapped_by_wrap_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A module first imported while the case's arguments are built ($new) is
    # loaded after start(); its classes have to be wrapped before the call.
    recorder = probe.InstanceRecorder(str(tmp_path), _PACKAGE)
    recorder.start()
    model, service = _instance_project(tmp_path, monkeypatch)

    recorder.wrap_loaded()
    service.build()
    recorder.active = False

    assert [(i["module"], i["class"]) for i in recorder.instances] == [
        ("model", "Repo")
    ]


def test_generated_dataclass_init_is_a_call_into_its_module_not_a_library(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # dataclasses generates __init__ with the module's globals but no file of
    # the project; it is still code of that module.
    _, service = _instance_project(tmp_path, monkeypatch)
    project = probe._Project(str(tmp_path), _PACKAGE)
    recorder = probe.CallRecorder(None, _PACKAGE, project, external=True)

    with recorder.watching():
        service.Service(repo=object()).other()

    edges = {(c["from"], c["module"], bool(c.get("external"))) for c in recorder.calls}
    assert ("service", "model", False) in edges
    assert not {edge for edge in edges if edge[2]}


_ALIAS_SERVICE = """
import os
import typing


class Pair(typing.NamedTuple):
    left: int
    right: int


def run(store, key):
    print(key)
    os.path.join("a", key)
    Pair(1, 2)
    return store.put(key)
"""


def test_libraries_go_by_their_import_name_and_generated_code_is_no_library(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The probe's own stdout is a plain buffer; pytest's capture would run
    # codecs under print() and show up as a library call.
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    modules = {
        "repo": _module(tmp_path, "repo", _REPO, monkeypatch),
        "service": _module(tmp_path, "service", _ALIAS_SERVICE, monkeypatch),
    }
    project = probe._Project(str(tmp_path), _PACKAGE)
    recorder = probe.CallRecorder(None, _PACKAGE, project, external=True)

    with recorder.watching():
        modules["service"].run(modules["repo"].Store(), "k")

    # os.path is posixpath (ntpath on Windows) underneath; print() talks to
    # the console and is no library; NamedTuple's __new__ is generated code.
    assert {c["module"] for c in recorder.calls if c.get("external")} == {"os"}


def test_a_constructor_run_by_new_is_recorded_whatever_loaded_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A constructor the case runs through $new is the project's code (a
    # service that builds its own repository there breaks injection). Its
    # classes may be loaded by that very $new, after start(): they are
    # wrapped before anything is constructed.
    recorder = probe.InstanceRecorder(str(tmp_path), _PACKAGE)
    recorder.start()
    _, service = _instance_project(tmp_path, monkeypatch)

    probe._build_value({"$new": "service.Service"}, vars(service), _PACKAGE)
    recorder.active = False

    assert [(i["module"], i["class"]) for i in recorder.instances] == [
        ("model", "Repo")
    ]


def test_a_class_first_imported_inside_the_call_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import builtins
    import importlib

    package = tmp_path / "lazy_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "models.py").write_text("class Thing:\n    pass\n", encoding="utf-8")
    (package / "svc.py").write_text(
        "def run():\n    from .models import Thing\n    return Thing()\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    for name in ("lazy_pkg", "lazy_pkg.models", "lazy_pkg.svc"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    # The import hooks are global; monkeypatch puts the originals back.
    monkeypatch.setattr(builtins, "__import__", builtins.__import__)
    monkeypatch.setattr(importlib, "__import__", importlib.__import__)
    monkeypatch.setattr(importlib, "import_module", importlib.import_module)
    probe.ImportRecorder(str(package)).install()
    svc = importlib.import_module("lazy_pkg.svc")
    recorder = probe.InstanceRecorder(str(package), "lazy_pkg")
    recorder.start()

    svc.run()
    recorder.active = False

    assert [(i["module"], i["class"]) for i in recorder.instances] == [
        ("models", "Thing")
    ]


def test_library_names_of_private_stdlib_modules() -> None:
    assert probe._library_name("_collections_abc") == "collections"
    assert probe._library_name("posixpath") == "os"
    assert probe._library_name("_pickle") == "pickle"


def test_a_finished_case_leaves_no_recorder_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, service = _instance_project(tmp_path, monkeypatch)
    recorder = probe.InstanceRecorder(str(tmp_path), _PACKAGE)

    _run_instances(service, "build", {"args": []}, recorder, kind="function")

    assert probe._RECORDING == []
