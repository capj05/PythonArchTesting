"""Subprocess entry point that runs dynamic checks against a target.

It calls target functions with the arguments of a rule's cases and reports
what the code did structurally: which other modules it called
(``forbid_runtime_calls``, ``require_runtime_calls``), which calls crossed
between the project's modules (``enforce_reference_calls``), which objects'
attributes it assigned from outside their class (``forbid_foreign_writes``),
which project classes it instantiated (``forbid_runtime_instantiation``), and
the order of flow stages (runtime ``enforce_flow``). In ``"imports"`` mode it records the
imports a target module performs while it is imported
(``forbid_runtime_imports``).

This file runs as a standalone script in a fresh interpreter, never as an
import of the framework, so it uses the standard library only. It reads one JSON
request from stdin and writes one JSON response to stdout. Anything the target
prints while it runs is redirected to stderr, so it cannot corrupt the response.
"""

from __future__ import annotations

import builtins
import contextlib
import dis
import enum
import importlib
import importlib.util
import inspect
import io
import itertools
import json
import os
import random
import signal
import sys
import threading
import time
import traceback
import types
from typing import Any, Iterable, Iterator

_REPR_LIMIT = 200
_MISSING = object()
# Frames running this file's own code (the write recorder's __setattr__
# wrapper, the case runner) are not target code and not a layer.
_PROBE_GLOBALS = globals()


class CaseSetupError(Exception):
    """A case could not be prepared, so the target was never called."""


class JobTimeout(BaseException):
    """Raised by the interval timer when one job of a batch runs too long.

    It derives from ``BaseException`` so ordinary ``except Exception`` blocks
    in target code do not swallow it; the probe's own broad handlers re-raise it.
    """


def _short_repr(value: Any) -> str:
    try:
        text = repr(value)
    except Exception as exc:  # pragma: no cover - defensive, repr rarely raises
        text = f"<unrepresentable {type(value).__name__}: {exc}>"
    if len(text) > _REPR_LIMIT:
        return text[: _REPR_LIMIT - 3] + "..."
    return text


def _describe_exception(exc: BaseException) -> str:
    """``"KeyError: 'id'"``, even for an exception whose ``__str__`` fails."""
    try:
        return f"{type(exc).__name__}: {exc}"
    except Exception:
        return f"{type(exc).__name__}: <unprintable>"


def _resolve_name(name: str, namespace: dict[str, Any], package: str | None) -> Any:
    head, _, rest = name.partition(".")
    if head in namespace:
        value = namespace[head]
    elif package:
        try:
            value = importlib.import_module(f"{package}.{head}")
        except ImportError as exc:
            raise CaseSetupError(f"cannot resolve {name!r}: {exc}") from exc
    else:
        raise CaseSetupError(f"cannot resolve {name!r} in the target module")
    for part in rest.split(".") if rest else ():
        parent, value = value, getattr(value, part, _MISSING)
        if value is _MISSING and hasattr(parent, "__path__"):
            # A submodule nothing imported yet: "domain.services.Service".
            try:
                value = importlib.import_module(f"{parent.__name__}.{part}")
            except ImportError:
                value = _MISSING
        if value is _MISSING:
            raise CaseSetupError(f"cannot resolve {name!r}: no attribute {part!r}")
    return value


# Calls received by spies (``{"$spy": name}`` in a case); reset per case.
_SPY_CALLS: list[dict[str, Any]] = []
# A rule only needs to know that a call happened; a target calling a spy in
# a long loop must not grow the response without bound.
_SPY_CALL_LIMIT = 1000
_FLOW_CALL_LIMIT = 5000


class _Spy:
    """A stand-in collaborator that records every call made on it.

    It is callable, and any attribute that is not a dunder is a method that
    records its call. A call returns the value ``returns`` gives for that
    member (``"__call__"`` for calling the spy itself), otherwise its first
    positional argument (or None), so a strategy or decorator chain that
    passes a value through keeps running and a query can be answered.
    """

    def __init__(self, name: str, returns: dict[str, Any] | None = None) -> None:
        object.__setattr__(self, "_spy_name", name)
        object.__setattr__(self, "_spy_returns", dict(returns or {}))

    def _answer(self, member: str, args: tuple[Any, ...]) -> Any:
        returns = object.__getattribute__(self, "_spy_returns")
        if member in returns:
            return returns[member]
        return args[0] if args else None

    def _record(
        self, member: str, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> Any:
        if len(_SPY_CALLS) >= _SPY_CALL_LIMIT:
            return self._answer(member, args)
        _SPY_CALLS.append(
            {
                "spy": object.__getattribute__(self, "_spy_name"),
                "member": member,
                "args": len(args) + len(kwargs),
            }
        )
        return self._answer(member, args)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._record("__call__", args, kwargs)

    def __getattr__(self, member: str) -> Any:
        if member.startswith("__"):
            raise AttributeError(member)

        def method(*args: Any, **kwargs: Any) -> Any:
            return self._record(member, args, kwargs)

        return method

    def __repr__(self) -> str:
        return f"<spy {object.__getattribute__(self, '_spy_name')}>"


# The instance recorder of the running case, if it records: a ``$new`` wraps
# the classes its import just loaded before it constructs anything, so what a
# constructor creates is recorded whichever module happened to load first.
_RECORDING: list[Any] = []


def _wrap_new_classes(loaded_before: int) -> None:
    """After an import that loaded modules, wrap their classes for recording.

    Code that imports a project module inside a function (a lazy import)
    loads its classes while the case runs; they are wrapped at once, so the
    objects the code goes on to create are recorded.
    """
    if len(sys.modules) == loaded_before:
        return
    for recorder in _RECORDING:
        if recorder.active:
            recorder.wrap_loaded()


def _build_value(value: Any, namespace: dict[str, Any], package: str | None) -> Any:
    if isinstance(value, dict) and "$spy" in value:
        returns = {
            str(member): _build_value(item, namespace, package)
            for member, item in (value.get("returns") or {}).items()
        }
        return _Spy(str(value["$spy"]), returns)
    if isinstance(value, dict) and "$new" in value:
        factory = _resolve_name(str(value["$new"]), namespace, package)
        for recorder in _RECORDING:
            recorder.wrap_loaded()
        args = [
            _build_value(item, namespace, package) for item in value.get("args", [])
        ]
        kwargs = {
            key: _build_value(item, namespace, package)
            for key, item in (value.get("kwargs") or {}).items()
        }
        try:
            return factory(*args, **kwargs)
        except JobTimeout:
            raise
        except BaseException as exc:
            raise CaseSetupError(
                f"constructing {value['$new']!r} raised {_describe_exception(exc)}"
            ) from exc
    if isinstance(value, list):
        return [_build_value(item, namespace, package) for item in value]
    if isinstance(value, dict):
        return {
            key: _build_value(item, namespace, package) for key, item in value.items()
        }
    return value


def _module_of(frame: Any) -> str | None:
    name = frame.f_globals.get("__name__") if frame is not None else None
    return str(name) if name else None


def _local_module(module: str | None, package: str | None) -> str | None:
    """``module`` without the package prefix the probe imported the target under.

    The package itself becomes ``__init__``, so a reference package and a
    target package with different names still name their modules alike.
    """
    if module and package and module.startswith(package + "."):
        return module[len(package) + 1 :]
    if module and package and module == package:
        return "__init__"
    return module


class _Project:
    """Which files and classes belong to the analysed project."""

    def __init__(self, target_root: str, package: str | None) -> None:
        self.root = os.path.realpath(target_root)
        self.package = package
        self._files: dict[str, str | None] = {}

    def relpath(self, filename: Any) -> str | None:
        """``filename`` relative to the root, or None when it lies outside."""
        if not filename:
            return None
        key = str(filename)
        if key.startswith("<") or not os.path.isabs(key):
            # "<frozen posixpath>", "<string>" (namedtuple, dataclass code):
            # resolved against the working directory, which is the target
            # root, they would pass for project files.
            return None
        if key not in self._files:
            path = os.path.realpath(key)
            inside = path == self.root or path.startswith(self.root + os.sep)
            self._files[key] = os.path.relpath(path, self.root) if inside else None
        return self._files[key]

    def classes(self) -> list[type]:
        """Classes defined in loaded project modules, bases before subclasses."""
        classes: list[type] = []
        for module in list(sys.modules.values()):
            if self.relpath(getattr(module, "__file__", None)) is None:
                continue
            for value in list(vars(module).values()):
                if (
                    isinstance(value, type)
                    and value.__module__ == module.__name__
                    and not issubclass(value, BaseException)
                    and not isinstance(value, enum.EnumMeta)
                ):
                    classes.append(value)
        return sorted(classes, key=lambda cls: len(cls.__mro__))


def _code_name(code: Any) -> str:
    # co_qualname exists from Python 3.11; co_name is the fallback.
    return str(getattr(code, "co_qualname", code.co_name))


_WRAPPER_NAMES = frozenset({"__setattr__", "__init__"})
# Builtins that do I/O, and the module a call of each is reported under.
_IO_BUILTINS = {"open": "io", "print": "builtins", "input": "builtins"}


# Modules a library's code runs in under another name than the one imported.
_LIBRARY_ALIASES = {
    "posixpath": "os",
    "ntpath": "os",
    "genericpath": "os",
    "_collections_abc": "collections",
}


def _library_name(module: str) -> str:
    """The name a project imports the library running in ``module`` under."""
    top = module.split(".")[0]
    top = _LIBRARY_ALIASES.get(top, top)
    if top.startswith("_") and top[1:] in sys.modules:
        top = top[1:]  # _pickle is pickle
    return top


def _generated(code: Any) -> bool:
    """Code compiled from a string (``<string>``), not a frozen module's."""
    name = str(code.co_filename)
    return name.startswith("<") and not name.startswith("<frozen")


def _c_callee(arg: Any) -> tuple[str, str] | None:
    """The module and name of a builtin or C function a frame calls.

    ``None`` for what belongs to no layer: ``len()``, ``list.append()``.
    """
    owner = getattr(arg, "__self__", None)
    module = getattr(arg, "__module__", None)
    if not module and owner is not None:
        # Methods of C types (``cursor.execute``) carry no __module__.
        module = getattr(type(owner), "__module__", None)
    name = getattr(arg, "__name__", None)
    io_module = _IO_BUILTINS.get(name) if name else None
    if io_module and getattr(builtins, str(name), None) is arg:
        # I/O is a layer of its own: open() is io.open, and print()
        # and input() talk to the console.
        return io_module, str(name)
    if module == "builtins" or (name and getattr(builtins, name, None) is arg):
        # len(), print(), list.append() belong to no layer; open() is
        # a builtin too, although it reports _io as its module.
        return None
    if not module:
        return None
    if module.startswith("_") and module[1:] in sys.modules:
        # pickle.dumps is _pickle.dumps; report the public module.
        module = module[1:]
    return str(module), str(getattr(arg, "__qualname__", arg))


class CallRecorder:
    """Record calls that cross from one module into another.

    A profile hook sees every call of a Python function (``"call"``, whose
    caller is the previous frame) and of a builtin or C function
    (``"c_call"``, made from the current frame).

    With ``caller_module`` set, a call counts when the caller is code of that
    module and the callee lives in another module, so helpers the module calls
    on itself are followed only through the calls they make outward. Without
    it (``project`` given instead), every call between two different modules
    of the project counts: the project's runtime dependency graph.

    With ``transitive`` (and ``project``) set as well, a call by other project
    code counts too while code of ``caller_module`` is further up the stack:
    it carries the ``origin`` (that code) and the project code ``via`` which
    the call was reached, outermost first.

    With ``external`` (and no ``caller_module``) a call from project code
    into a module outside the project counts as well, named by its top-level
    package and marked ``external``: the libraries the project uses. Only the
    boundary is recorded, never what the library calls in turn.
    """

    def __init__(
        self,
        caller_module: str | None,
        package: str | None,
        project: _Project | None = None,
        transitive: bool = False,
        external: bool = False,
    ) -> None:
        self._caller = caller_module
        self._external = external and caller_module is None and project is not None
        self._package = package
        self._project = project
        self._transitive = transitive and project is not None
        self.calls: list[dict[str, Any]] = []
        self._seen: set[tuple[Any, ...]] = set()

    def _note_through(self, caller: Any, module: str | None, callee: str) -> None:
        """Note a call by other code, if code of the caller module led to it."""
        if not self._in_project(caller):
            return
        chain = _origin_chain(
            caller, str(self._caller), self._package, self._in_project
        )
        if chain is not None:
            self._note(caller, module, callee, origin=chain[0], via=chain[1])

    def _note(
        self,
        caller: Any,
        module: str | None,
        callee: str,
        origin: dict[str, Any] | None = None,
        via: list[dict[str, Any]] | None = None,
        external: bool = False,
    ) -> None:
        source = _module_of(caller)
        if not module:
            return
        if external:
            module = _library_name(module)
        caller_name = _code_name(caller.f_code)
        local = module == source
        if local and caller_name.split(".")[0] == callee.split(".")[0]:
            # Within one class or function: never a call between two parts
            # of the architecture. Calls between two top-level entities of
            # one module are kept, marked local: a target may keep several
            # layers in one module, and only the entities tell them apart.
            return
        chain = tuple((step["module"], step["caller"]) for step in via or ())
        key: tuple[Any, ...] = (
            str(source),
            module,
            callee,
            caller.f_lineno,
            chain,
            external,
        )
        if key in self._seen:
            return
        self._seen.add(key)
        call: dict[str, Any] = {
            "from": _local_module(source, self._package),
            "module": _local_module(module, self._package),
            "callee": callee,
            "caller": caller_name,
            "line": caller.f_lineno,
        }
        file = (
            self._project.relpath(caller.f_code.co_filename) if self._project else None
        )
        if file is not None:
            # Where the call was made, relative to the target root.
            call["file"] = file
        if local:
            call["local"] = True
        if external:
            call["external"] = True
        if origin is not None:
            call["origin"] = origin
            call["via"] = list(via or [])
        self.calls.append(call)

    def _in_project(self, frame: Any) -> bool:
        return (
            self._project is not None
            and frame is not None
            and frame.f_globals is not _PROBE_GLOBALS
            and self._project.relpath(frame.f_code.co_filename) is not None
        )

    def profile(self, frame: Any, event: str, arg: Any) -> None:
        if event == "call":
            if frame.f_globals is _PROBE_GLOBALS:
                return
            caller = frame.f_back
            while (
                caller is not None
                and caller.f_globals is _PROBE_GLOBALS
                and caller.f_code.co_name in _WRAPPER_NAMES
            ):
                # A setter or constructor run by a recorder's wrapper is
                # called by the code that made the assignment or the object.
                caller = caller.f_back
            if self._caller is None:
                if self._in_project(caller) and (
                    self._in_project(frame) or self._generated_in_project(frame)
                ):
                    self._note(caller, _module_of(frame), _code_name(frame.f_code))
                elif (
                    self._external
                    and self._in_project(caller)
                    and not _generated(frame.f_code)
                ):
                    # Code generated from a string (a NamedTuple's __new__)
                    # belongs to no library.
                    self._note(
                        caller,
                        _module_of(frame),
                        _code_name(frame.f_code),
                        external=True,
                    )
            elif _module_of(caller) == self._caller:
                self._note(caller, _module_of(frame), _code_name(frame.f_code))
            elif self._transitive:
                self._note_through(caller, _module_of(frame), _code_name(frame.f_code))
        elif event == "c_call" and self._external and self._in_project(frame):
            target = _c_callee(arg)
            if (
                target is not None
                and target[0] != "builtins"  # print() and input(): the console
                and not self._is_project_module(target[0])
            ):
                self._note(frame, target[0], target[1], external=True)
        elif event == "c_call" and self._caller is not None:
            note: Any = self._note if _module_of(frame) == self._caller else None
            if note is None and self._transitive and self._in_project(frame):
                note = self._note_through
            if note is None:
                return
            target = _c_callee(arg)
            if target is not None:
                note(frame, target[0], target[1])

    def _generated_in_project(self, frame: Any) -> bool:
        """Code generated for a project module, with no file of its own.

        ``dataclasses`` builds ``__init__`` from a string, with the globals of
        the class's module: it is that module's code all the same.
        """
        module = _module_of(frame)
        return (
            frame.f_globals is not _PROBE_GLOBALS
            and _generated(frame.f_code)
            and module is not None
            and self._is_project_module(module)
        )

    def _is_project_module(self, module: str) -> bool:
        package = self._package
        return bool(package) and (module == package or module.startswith(f"{package}."))

    @contextlib.contextmanager
    def watching(self) -> Iterator[None]:
        # threading.setprofile covers threads the target starts meanwhile.
        previous = sys.getprofile()
        previous_threads = threading.getprofile()
        sys.setprofile(self.profile)
        threading.setprofile(self.profile)
        try:
            yield
        finally:
            sys.setprofile(previous)
            threading.setprofile(previous_threads)


_MAX_WRAPPED = 16  # bounds a __wrapped__ chain that loops back on itself


def _codes_of(function: Any) -> list[Any]:
    """Code objects of ``function`` and of what it wraps (``__wrapped__``).

    A constructor wrapped by ``InstanceRecorder`` (or a method behind a
    ``functools.wraps`` decorator) still runs its own code.
    """
    codes: list[Any] = []
    for _ in range(_MAX_WRAPPED):
        if function is None:
            break
        code = getattr(function, "__code__", None)
        if code is not None:
            codes.append(code)
        function = getattr(function, "__wrapped__", None)
    return codes


class LineRecorder:
    """Record which lines of the target's own code a case executes.

    A dynamic check sees only the code that runs, so a line no case reaches
    was not checked. The target's code is the innermost function behind any
    ``__wrapped__`` chain, together with the functions, lambdas and
    comprehensions nested in it; a line counts as executable when its code
    object maps an instruction to it.
    """

    def __init__(self, function: Any, project: _Project) -> None:
        codes = _codes_of(getattr(function, "__func__", function))
        self._codes: set[Any] = set()
        self.executable: set[int] = set()
        self.executed: set[int] = set()
        self.file = project.relpath(codes[-1].co_filename) if codes else None
        pending = codes[-1:]
        while pending:
            code = pending.pop()
            self._codes.add(code)
            self.executable.update(
                line for _, _, line in code.co_lines() if line is not None
            )
            pending.extend(c for c in code.co_consts if isinstance(c, types.CodeType))

    def _line(self, frame: Any, event: str, arg: Any) -> Any:
        _ = arg
        if event == "line":
            self.executed.add(frame.f_lineno)
        return self._line

    def _call(self, frame: Any, event: str, arg: Any) -> Any:
        _ = event, arg
        if frame.f_code not in self._codes:
            return None
        self.executed.add(frame.f_code.co_firstlineno)
        return self._line

    @contextlib.contextmanager
    def watching(self) -> Iterator[None]:
        previous = sys.gettrace()
        previous_threads = threading.gettrace()
        sys.settrace(self._call)
        threading.settrace(self._call)
        try:
            yield
        finally:
            sys.settrace(previous)
            threading.settrace(previous_threads)

    def report(self) -> dict[str, Any] | None:
        if self.file is None or not self.executable:
            return None
        return {
            "file": self.file,
            "run": sorted(self.executable & self.executed),
            "missed": sorted(self.executable - self.executed),
        }


_THREAD_GRACE_S = 1.0


@contextlib.contextmanager
def _joining_new_threads() -> Iterator[None]:
    """Wait, briefly, for the threads the target started to finish.

    What a thread does after the case returns would otherwise be lost to the
    observers. Daemon threads are not waited for, and the wait as a whole is
    bounded, so a worker that never ends costs one second, not the job.
    """
    before = set(threading.enumerate())
    try:
        yield
    finally:
        deadline = time.monotonic() + _THREAD_GRACE_S
        for thread in threading.enumerate():
            if thread in before or thread.daemon:
                continue
            thread.join(max(0.0, deadline - time.monotonic()))


class WriteRecorder:
    """Record attribute assignments made from outside the object's own class.

    Every class defined in a module under the target root gets a
    ``__setattr__`` wrapper. While ``active`` is set, an assignment counts as
    foreign unless the assigning code is a method of the object's class or one
    of its bases (including properties, class and static methods), or the
    attribute is a property with a setter, which the class itself runs. Code nested
    inside a method (a lambda, a local helper) counts as outside it.
    Assignments made by code outside the target root (the standard library,
    the probe) are ignored.

    Changes that bypass ``__setattr__`` are found by comparison instead
    (``watching``): the instances the case can reach are snapshotted — which
    object each attribute holds and, for a builtin container, what it holds —
    and compared wherever a change can have happened: after a C method of a
    container they hold returns (``append``, ``update``), after ``delattr``,
    after library code that was handed one of them returns
    (``random.shuffle``), on every call and return of project code whose
    bytecode can change state without a call (``x[i] = ...``, ``del``,
    ``+=``, ``__dict__``, ``object.__setattr__``), and when project code
    returns to its caller outside the project. A difference belongs to the
    nearest project code that ran since the last comparison. It is recorded
    with its ``change``: ``mutated`` (what a container holds), ``deleted``, or
    ``bypassed`` (``obj.__dict__[...]``, ``object.__setattr__``); an ordinary
    assignment is ``assigned``.
    """

    _MARK = "__pat_write_recorder__"

    def __init__(self, target_root: str, package: str | None = None) -> None:
        self._project = _Project(target_root, package)
        self._package = package
        self.active = False
        self.writes: list[dict[str, Any]] = []
        self._seen: set[tuple[str, str, str, int]] = set()
        self._method_codes: dict[type, set[Any]] = {}
        self._classes: set[type] = set()
        # id -> (object, snapshot); the object is held so its id stays unique.
        self._watched: dict[int, tuple[Any, dict[str, Any]]] = {}
        self._project_codes: dict[Any, bool] = {}
        self._changing_codes: dict[Any, bool] = {}
        # Container id (a __dict__ included) -> ids of the watched instances
        # holding it; a C method of the container can change only those.
        self._held: dict[int, set[int]] = {}
        # Library frames handed a watched object or container, compared on return.
        self._library: set[Any] = set()

    def start(self, roots: Iterable[Any] = ()) -> None:
        """Begin recording one case, wrapping classes imported since the last.

        ``roots`` (the case's arguments, the instance a method runs on) and
        the project instances they hold are watched for changes that bypass
        ``__setattr__``; instances built while the case runs are added as
        they are.
        """
        self.install()
        self.writes = []
        self._seen = set()
        self._classes = set(self._project.classes())
        self._watched = {}
        self._held = {}
        self._library = set()
        self._collect(roots)
        self.active = True

    def _collect(self, roots: Iterable[Any]) -> None:
        pending = [(root, 0) for root in roots]
        visited: set[int] = set()
        while pending:
            obj, depth = pending.pop()
            if id(obj) in visited or depth > _WATCH_DEPTH:
                continue
            visited.add(id(obj))
            if type(obj) in self._classes:
                self._watch(obj)
                values = list(getattr(obj, "__dict__", {}).values())
            elif isinstance(obj, (list, tuple, set, frozenset)):
                values = list(obj)
            elif isinstance(obj, dict):
                values = list(obj.values())
            else:
                continue
            pending.extend((value, depth + 1) for value in values)

    def _watch(self, obj: Any) -> None:
        snapshot = _snapshot(obj)
        if snapshot is not None:
            self._watched[id(obj)] = (obj, snapshot)
            self._note_held(obj)

    def _note_held(self, obj: Any) -> None:
        """Remember the containers ``obj`` holds, whose methods can change it."""
        state = getattr(obj, "__dict__", None)
        if isinstance(state, dict):
            self._held.setdefault(id(state), set()).add(id(obj))
            for value in list(state.values()):
                if type(value) in _CONTAINERS:
                    self._held.setdefault(id(value), set()).add(id(obj))

    def _in_project(self, frame: Any) -> bool:
        if frame is None or frame.f_globals is _PROBE_GLOBALS:
            return False
        code = frame.f_code
        known = self._project_codes.get(code)
        if known is None:
            known = self._project.relpath(code.co_filename) is not None
            self._project_codes[code] = known
        return known

    def _may_change(self, code: Any) -> bool:
        """Whether ``code`` can change state with no call the profiler sees."""
        known = self._changing_codes.get(code)
        if known is None:
            known = bool(_BYPASS_NAMES.intersection(code.co_names)) or any(
                instr.opname in _CHANGING_OPS
                or instr.opname.startswith("INPLACE_")
                or (instr.opname == "BINARY_OP" and "=" in instr.argrepr)
                for instr in dis.get_instructions(code)
            )
            self._changing_codes[code] = known
        return known

    def _refresh(self, obj: Any, name: str) -> None:
        """Take an assignment ``__setattr__`` saw into the snapshot."""
        entry = self._watched.get(id(obj))
        if entry is None or entry[0] is not obj:
            if type(obj) in self._classes:
                self._watch(obj)
            return
        state = getattr(obj, "__dict__", {})
        if name in state:
            entry[1][name] = _fingerprint(state[name])
            if type(state[name]) in _CONTAINERS:
                self._held.setdefault(id(state[name]), set()).add(id(obj))
        else:
            entry[1].pop(name, None)

    @contextlib.contextmanager
    def watching(self) -> Iterator[None]:
        """Compare the watched instances wherever a change can have happened."""
        # Chained: calls may be recorded by a profile function of their own.
        previous: Any = sys.getprofile()
        previous_threads = threading.getprofile()

        def profile(frame: Any, event: str, arg: Any) -> None:
            if self.active:
                self._event(frame, event, arg)
            if previous is not None:
                previous(frame, event, arg)

        sys.setprofile(profile)
        threading.setprofile(profile)
        try:
            yield
        finally:
            sys.setprofile(previous)
            threading.setprofile(previous_threads)

    def _event(self, frame: Any, event: str, arg: Any) -> None:
        if frame.f_globals is _PROBE_GLOBALS:
            return  # the recorders' own code; they keep the snapshots current
        if event == "c_return":
            if not self._in_project(frame):
                return
            holders = self._held.get(id(getattr(arg, "__self__", None)))
            if holders:
                self._compare(frame, holders)
            elif arg is delattr:
                self._compare(frame)
        elif event == "call":
            caller = frame.f_back
            if not self._in_project(caller):
                return
            if self._may_change(caller.f_code):
                self._compare(caller)
            if not self._in_project(frame) and any(
                id(value) in self._held or id(value) in self._watched
                for value in list(frame.f_locals.values())
            ):
                self._library.add(frame)
        elif event == "return":
            if frame in self._library:
                self._library.discard(frame)
                self._compare(frame)
                return
            if not self._in_project(frame):
                return
            if frame.f_code.co_name == "__init__":
                built = frame.f_locals.get(next(iter(frame.f_code.co_varnames), ""))
                if type(built) in self._classes and id(built) not in self._watched:
                    self._watch(built)
            if self._may_change(frame.f_code) or not self._in_project(frame.f_back):
                self._compare(frame)

    def _compare(self, ran: Any, keys: Iterable[int] | None = None) -> None:
        """Record what changed since the last comparison, made by ``ran``.

        ``keys`` limits the comparison to those watched instances.
        """
        writer = ran
        while writer is not None and not self._in_project(writer):
            writer = writer.f_back
        entries = (
            list(self._watched.items())
            if keys is None
            else [
                (key, self._watched[key]) for key in list(keys) if key in self._watched
            ]
        )
        for key, (obj, before) in entries:
            after = _snapshot(obj)
            if after is None or after == before:
                continue
            self._watched[key] = (obj, after)
            self._note_held(obj)
            if writer is None or self._owns(writer, obj):
                continue
            for name in sorted(set(before) | set(after)):
                old, new = before.get(name), after.get(name)
                if old == new:
                    continue
                if new is None:
                    change = "deleted"
                elif old is not None and old[0] == new[0]:
                    change = "mutated"
                else:
                    change = "bypassed"
                self._record(obj, name, writer, change)

    def install(self) -> None:
        """Wrap every target class loaded so far; safe to call repeatedly."""
        # Bases come first, so a subclass that inherits a wrapper is skipped.
        for cls in self._project.classes():
            if getattr(cls.__setattr__, self._MARK, False):
                continue
            self._wrap(cls)

    def _wrap(self, cls: type) -> None:
        # The unbound slot takes the instance first, which type's own
        # signature for __setattr__ does not describe.
        original: Any = cls.__setattr__
        recorder = self

        def __setattr__(obj: Any, name: str, value: Any) -> None:
            if recorder.active:
                recorder._check(obj, name, sys._getframe(1))
            original(obj, name, value)
            if recorder.active:
                recorder._refresh(obj, name)

        setattr(__setattr__, self._MARK, True)
        # A class's own __setattr__ that calls super().__setattr__ is the
        # class's code; _owns finds it through __wrapped__.
        setattr(__setattr__, "__wrapped__", original)
        try:
            cls.__setattr__ = __setattr__  # type: ignore[assignment]
        except (TypeError, AttributeError):
            pass  # a class that refuses it is simply not observed

    def _owns(self, frame: Any, obj: Any) -> bool:
        """Whether the assigning code is a method of the object's class.

        Methods are found through the class dictionaries along the MRO, so
        inherited methods, properties, class and static methods all count,
        and a plain function that merely receives the object does not. A
        method behind a decorator that does not set ``__wrapped__`` is not in
        the class dictionary, so code whose qualified name places it directly
        in one of the classes, in that class's module, counts too; a function
        nested in a method (``Cls.method.<locals>.helper``) does not.
        """
        cls = type(obj)
        codes = self._method_codes.get(cls)
        if codes is None:
            codes = set()
            for klass in cls.__mro__:
                for member in vars(klass).values():
                    if isinstance(member, property):
                        functions = [member.fget, member.fset, member.fdel]
                    else:
                        functions = [getattr(member, "__func__", member)]
                    for function in functions:
                        codes.update(_codes_of(function))
            self._method_codes[cls] = codes
        if frame.f_code in codes:
            return True
        owner = _code_name(frame.f_code).rpartition(".")[0]
        module = frame.f_globals.get("__name__")
        return any(
            klass.__qualname__ == owner and klass.__module__ == module
            for klass in cls.__mro__
        )

    def _check(self, obj: Any, name: str, frame: Any) -> None:
        relpath = self._project.relpath(frame.f_code.co_filename)
        if relpath is None or self._owns(frame, obj):
            return
        descriptor = inspect.getattr_static(type(obj), name, None)
        if isinstance(descriptor, property) and descriptor.fset is not None:
            return  # the class's own setter decides what the assignment does
        self._record(obj, name, frame, "assigned")

    def _record(self, obj: Any, name: str, frame: Any, change: str) -> None:
        relpath = self._project.relpath(frame.f_code.co_filename)
        owner = type(obj).__qualname__
        module = _local_module(_module_of(frame), self._package)
        writer = f"{module}:{_code_name(frame.f_code)}"
        key = (owner, name, writer, frame.f_lineno)
        if key in self._seen:
            return
        self._seen.add(key)
        self.writes.append(
            {
                "class": owner,
                "attribute": name,
                "writer": writer,
                "file": relpath,
                "line": frame.f_lineno,
                "change": change,
            }
        )


_WATCH_DEPTH = 3  # how deep the case's arguments are searched for instances
_CONTENT_LIMIT = 1000  # a larger container is compared by its length only


class _Held:
    """What a builtin container holds: a shallow copy, compared item by item.

    Equal items compare in C, unchanged ones by identity alone, so comparing
    costs little more than copying. An item that cannot say whether it equals
    itself (an array with an elementwise ``==``) makes the copy differ.
    """

    __slots__ = ("items",)

    def __init__(self, value: Any) -> None:
        self.items: Any = (
            len(value) if len(value) > _CONTENT_LIMIT else type(value)(value)
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _Held):
            return NotImplemented
        try:
            return bool(self.items == other.items)
        except Exception:  # noqa: BLE001 - any failure to compare is a change
            return False

    __hash__ = None  # type: ignore[assignment]


_CONTAINERS = (list, dict, set, bytearray)
# Bytecode that changes state without a call the profiler would report.
_CHANGING_OPS = frozenset(
    {"STORE_SUBSCR", "DELETE_SUBSCR", "DELETE_ATTR", "STORE_SLICE"}
)
# Names through which code writes past a class's __setattr__.
_BYPASS_NAMES = frozenset({"__dict__", "__setattr__", "__delattr__"})


def _fingerprint(value: Any) -> tuple[int, Any]:
    """Which object ``value`` is and, for a builtin container, what it holds."""
    if type(value) in _CONTAINERS:
        return id(value), _Held(value)
    return id(value), None


def _snapshot(obj: Any) -> dict[str, Any] | None:
    state = getattr(obj, "__dict__", None)
    if not isinstance(state, dict):
        return None
    return {name: _fingerprint(value) for name, value in list(state.items())}


def _origin_chain(
    frame: Any, origin_module: str, package: str | None, in_project: Any
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    """The code of ``origin_module`` up the stack from ``frame``, and the way there.

    Returns the origin (``from``, ``caller``, and ``line``, the line of that
    code the way out starts at) and the project code ``via`` which it reached
    ``frame``, outermost first, ``frame`` included; ``None`` when no code of
    ``origin_module`` is on the stack.
    """
    via: list[dict[str, Any]] = []
    while frame is not None:
        if frame.f_globals is _PROBE_GLOBALS:
            if frame.f_code.co_name not in _WRAPPER_NAMES:
                return None  # the probe's own driver: the case started here
            # A recorder's wrapper around a constructor or __setattr__.
            frame = frame.f_back
            continue
        if _module_of(frame) == origin_module:
            via.reverse()
            origin = {
                "from": _local_module(origin_module, package),
                "caller": _code_name(frame.f_code),
                "line": frame.f_lineno,
            }
            return origin, via
        if in_project(frame):
            via.append(
                {
                    "module": _local_module(_module_of(frame), package),
                    "caller": _code_name(frame.f_code),
                }
            )
        frame = frame.f_back
    return None


class InstanceRecorder:
    """Record which project code creates instances of the project's classes.

    Every class defined under the target root gets an ``__init__`` wrapper
    that, while ``active`` is set, notes the object's class and the frame that
    asked for it. Only the outermost constructor of an object counts, so a
    ``super().__init__()`` chain is one instantiation of the most derived class.
    Objects created by code outside the target root (the probe building case
    arguments, the standard library) are ignored.

    With an ``origin`` module given to ``start``, an object built by other
    code while code of that module is further up the stack carries the
    ``origin`` and the project code ``via`` which it was built, as transitive
    calls do in ``CallRecorder``.
    """

    _MARK = "__pat_instance_recorder__"

    def __init__(self, target_root: str, package: str | None = None) -> None:
        self._project = _Project(target_root, package)
        self._package = package
        self.active = False
        self.instances: list[dict[str, Any]] = []
        self._seen: set[tuple[str, str, int]] = set()
        self._building: set[int] = set()
        self._origin: str | None = None

    def _in_project(self, frame: Any) -> bool:
        return (
            frame.f_globals is not _PROBE_GLOBALS
            and self._project.relpath(frame.f_code.co_filename) is not None
        )

    def start(self, origin: str | None = None) -> None:
        """Begin recording one case, wrapping classes imported since the last."""
        self._origin = origin
        _RECORDING[:] = [self]
        self.wrap_loaded()
        self.instances = []
        self._seen = set()
        self.active = True

    def stop(self) -> None:
        """End recording one case; the recorder no longer wraps new classes."""
        self.active = False
        if self in _RECORDING:
            _RECORDING.remove(self)

    def wrap_loaded(self) -> None:
        """Wrap the classes of project modules imported since the last call."""
        for cls in self._project.classes():
            klass: Any = cls  # the unbound constructor, which mypy reads as bound
            if not getattr(klass.__init__, self._MARK, False):
                self._wrap(cls)

    def _wrap(self, cls: type) -> None:
        klass: Any = cls
        original: Any = klass.__init__
        bare = original is object.__init__
        recorder = self

        def __init__(obj: Any, *args: Any, **kwargs: Any) -> None:
            key = id(obj)
            if key in recorder._building:
                original(obj, *args, **kwargs)
                return
            recorder._building.add(key)
            try:
                if recorder.active:
                    recorder._note(obj, sys._getframe(1))
                if bare:
                    # object.__init__ rejects arguments once __init__ is
                    # overridden; the arguments belonged to __new__.
                    original(obj)
                else:
                    original(obj, *args, **kwargs)
            finally:
                recorder._building.discard(key)

        setattr(__init__, self._MARK, True)
        # WriteRecorder follows this to the constructor's own code.
        setattr(__init__, "__wrapped__", original)
        try:
            cls.__init__ = __init__  # type: ignore[misc]
        except (TypeError, AttributeError):
            pass  # a class that refuses it is simply not observed

    def _note(self, obj: Any, frame: Any) -> None:
        relpath = self._project.relpath(frame.f_code.co_filename)
        if relpath is None:
            return
        cls = type(obj)
        source = _local_module(_module_of(frame), self._package)
        key = (cls.__qualname__, str(source), frame.f_lineno)
        if key in self._seen:
            return
        self._seen.add(key)
        instance: dict[str, Any] = {
            "class": cls.__qualname__,
            "module": _local_module(cls.__module__, self._package),
            "from": source,
            "creator": f"{source}:{_code_name(frame.f_code)}",
            "file": relpath,
            "line": frame.f_lineno,
        }
        if self._origin is not None and _module_of(frame) != self._origin:
            chain = _origin_chain(frame, self._origin, self._package, self._in_project)
            if chain is not None:
                instance["origin"], instance["via"] = chain
        self.instances.append(instance)


class ImportRecorder:
    """Record the imports that target code performs while the probe runs.

    ``builtins.__import__`` covers ``import`` statements and ``__import__("x")``;
    ``importlib.import_module`` is wrapped separately because it bypasses it. An
    import counts only when the importing frame's file lies under the target
    root, so imports made by the standard library on its own are ignored.
    """

    def __init__(self, target_root: str) -> None:
        self._root = os.path.realpath(target_root)
        self.phase = "import"
        self.events: list[dict[str, Any]] = []

    def _caller_file(self, frame: Any) -> str | None:
        filename = frame.f_globals.get("__file__") if frame is not None else None
        if not filename:
            return None
        path = os.path.realpath(filename)
        if path != self._root and not path.startswith(self._root + os.sep):
            return None
        return os.path.relpath(path, self._root)

    def _note(
        self,
        name: str,
        frame: Any,
        package: str | None,
        level: int,
        fromlist: Any,
    ) -> None:
        relpath = self._caller_file(frame)
        if relpath is None:
            return
        try:
            absolute = (
                importlib.util.resolve_name("." * level + name, package)
                if level
                else name
            )
        except (ImportError, ValueError):
            absolute = name
        # "from x.y import z" records only "x.y.z", like "import x.y.z" would:
        # the parent package is a precondition, not the dependency itself, and
        # recording it would defeat an allow-list entry for "x.y.z".
        items = [item for item in fromlist or () if item != "*"]
        names = [f"{absolute}.{item}" for item in items] or [absolute]
        for module_name in names:
            self.events.append(
                {
                    "module": module_name,
                    "phase": self.phase,
                    "file": relpath,
                    "line": frame.f_lineno,
                }
            )

    def install(self) -> None:
        original_import = builtins.__import__
        original_import_module = importlib.import_module

        def hooked_import(
            name: str,
            globals: Any = None,  # noqa: A002 - mirrors builtins.__import__
            locals: Any = None,  # noqa: A002
            fromlist: Any = (),
            level: int = 0,
        ) -> Any:
            frame = sys._getframe(1)
            package = _importing_package(globals) if level else None
            self._note(name, frame, package, level, fromlist)
            loaded = len(sys.modules)
            module = original_import(name, globals, locals, fromlist, level)
            _wrap_new_classes(loaded)
            return module

        def hooked_import_module(name: str, package: str | None = None) -> Any:
            level = len(name) - len(name.lstrip("."))
            self._note(name.lstrip("."), sys._getframe(1), package, level, ())
            loaded = len(sys.modules)
            module = original_import_module(name, package)
            _wrap_new_classes(loaded)
            return module

        builtins.__import__ = hooked_import
        # importlib.__import__ is a separate function with the same contract.
        importlib.__import__ = hooked_import
        importlib.import_module = hooked_import_module

    def forbidden_hits(
        self,
        forbidden: list[str],
        allow: list[str],
        phases: set[str],
        package: str | None = None,
    ) -> list[dict[str, Any]]:
        """Recorded imports of a ``forbidden`` module that ``allow`` does not lift.

        A project module is named as the reference names it, without the
        package the probe imported the target under: inside package ``t``,
        ``from . import repository`` imports ``t.repository``, which
        ``"repository"`` forbids.
        """

        def matches(module_name: str, prefix: str) -> bool:
            local = _local_module(module_name, package) or module_name
            return any(
                name == prefix or name.startswith(prefix + ".")
                for name in (module_name, local)
            )

        hits: list[dict[str, Any]] = []
        seen: set[tuple[str, str, int]] = set()
        for event in self.events:
            if event["phase"] not in phases:
                continue
            module_name = event["module"]
            if not any(matches(module_name, prefix) for prefix in forbidden):
                continue
            if any(matches(module_name, prefix) for prefix in allow):
                continue
            key = (module_name, event["file"], event["line"])
            if key not in seen:
                seen.add(key)
                hits.append(event)
        return hits


def _importing_package(globals_: Any) -> str | None:
    globals_ = globals_ or {}
    package = globals_.get("__package__")
    if package:
        return str(package)
    spec = globals_.get("__spec__")
    return getattr(spec, "parent", None) or None


def _call_with_trace(
    func: Any,
    args: list[Any],
    kwargs: dict[str, Any],
    project: _Project,
    stage_spans: list[dict[str, Any]] | None = None,
    stages: list[list[Any]] | None = None,
    calls: list[dict[str, str]] | None = None,
) -> Any:
    """Call ``func`` and record which project functions it calls, in order.

    Only calls into functions and methods defined in the analysed project
    count; the standard library and builtins (``str.strip``) are not part of
    the program's structure. Values are never recorded.

    With ``calls``, every such call made anywhere below ``func`` is appended
    as ``{"module", "qualname"}`` (up to ``_FLOW_CALL_LIMIT``).

    With ``stage_spans`` (``{"stage", "start", "end"}`` line ranges of
    flow-annotated statements of ``func``), each time execution leaves such a
    statement, ``[stage, calls]`` is appended to ``stages``, where ``calls``
    are the project functions ``func`` called directly while that statement
    was the innermost one running: the operations the stage consists of.
    """
    spans = list(stage_spans or [])
    code = getattr(inspect.unwrap(getattr(func, "__func__", func)), "__code__", None)
    if code is None:
        raise CaseSetupError("trace needs a Python function, not a builtin")
    if code.co_flags & (
        inspect.CO_GENERATOR | inspect.CO_COROUTINE | inspect.CO_ASYNC_GENERATOR
    ):
        # Calling it only creates the generator or coroutine; its body runs
        # later, after the tracer has been removed.
        raise CaseSetupError("trace does not support generators or coroutines")
    root: list[Any] = []

    # Spans nest: a marker after an ``if`` or ``for`` labels the whole block,
    # which can contain other labelled statements. A span is active from the
    # first line event inside its range until the first line event outside it
    # (or the return), and only then has its statement finished. Each active
    # entry is [span, calls made while it was the innermost active span].
    active: list[list[Any]] = []

    def update_spans(lineno: int | None) -> None:
        def inside(span: dict[str, Any]) -> bool:
            return lineno is not None and span["start"] <= lineno <= span["end"]

        # Finish the innermost (most recently entered) spans first.
        for entry in reversed(list(active)):
            if not inside(entry[0]):
                active.remove(entry)
                if stages is not None:
                    stages.append([entry[0]["stage"], entry[1]])
        for span in sorted(spans, key=lambda s: s["start"] - s["end"]):
            if inside(span) and not any(span is entry[0] for entry in active):
                active.append([span, []])

    def local_tracer(frame: Any, event: str, arg: Any) -> Any:
        _ = arg
        if spans and frame is root[0] and event in ("line", "return"):
            # A "line" event fires before its line runs, so a span whose
            # range we have just left holds a finished statement.
            update_spans(frame.f_lineno if event == "line" else None)
        return local_tracer

    def note_call(frame: Any) -> None:
        if frame.f_globals is _PROBE_GLOBALS or frame.f_code.co_name.startswith("<"):
            return
        if project.relpath(frame.f_code.co_filename) is None:
            return
        callee = {
            "module": str(_local_module(_module_of(frame), project.package)),
            "qualname": _code_name(frame.f_code),
        }
        if calls is not None and len(calls) < _FLOW_CALL_LIMIT:
            calls.append(callee)
        if active and frame.f_back is root[0]:
            active[-1][1].append(callee)

    def global_tracer(frame: Any, event: str, arg: Any) -> Any:
        _ = arg
        if event != "call":
            return None
        if not root:
            if frame.f_code is code:
                root.append(frame)
                return local_tracer
            return None
        note_call(frame)
        return None

    previous = sys.gettrace()
    sys.settrace(global_tracer)
    try:
        result = func(*args, **kwargs)
    finally:
        replaced = sys.gettrace() is not global_tracer
        sys.settrace(previous)
        if replaced:
            # A target that installs or clears a tracer silently ends ours;
            # an empty trace would then read as an ordinary mismatch.
            raise CaseSetupError("the target replaced the trace function")
    return result


def _accepts_positional(value: Any, arity: int) -> bool:
    """Whether ``value`` can be called with ``arity`` positional arguments.

    Keyword-only parameters without a default do not count against it: the
    probe only knows how many positional arguments the protocol passes. A
    callable without an introspectable signature gets the benefit of the
    doubt.
    """
    try:
        signature = inspect.signature(value)
    except (TypeError, ValueError):
        return True
    try:
        bound = signature.bind_partial(*([None] * arity))
    except TypeError:
        return False
    skipped = (
        inspect.Parameter.VAR_POSITIONAL,
        inspect.Parameter.VAR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    )
    return all(
        name in bound.arguments
        or param.default is not inspect.Parameter.empty
        or param.kind in skipped
        for name, param in signature.parameters.items()
    )


def _member_where(obj: Any, name: str, static: Any) -> str:
    instance_dict = getattr(obj, "__dict__", None)
    if isinstance(static, types.MemberDescriptorType) or (
        isinstance(instance_dict, dict) and name in instance_dict
    ):
        return "instance"
    owner = next((klass for klass in type(obj).__mro__ if name in vars(klass)), None)
    return f"{owner.__module__}.{owner.__qualname__}" if owner else "dynamic"


def _member_type(
    obj: Any, name: str, class_name: str, namespace: dict[str, Any], package: str | None
) -> dict[str, Any]:
    """Whether member ``name`` of ``obj`` holds an instance of ``class_name``."""
    try:
        value = getattr(obj, name)
        expected = _resolve_name(class_name, namespace, package)
    except JobTimeout:
        raise
    except BaseException as exc:
        return {"type_ok": False, "type_error": _describe_exception(exc)}
    if not isinstance(expected, type):
        return {"type_ok": False, "type_error": f"{class_name} is not a class"}
    return {"type": type(value).__qualname__, "type_ok": isinstance(value, expected)}


def _describe_member(obj: Any, name: str, arity: int | None) -> dict[str, Any]:
    """Whether ``obj`` has ``name`` at run time, and where it comes from.

    ``getattr_static`` finds data attributes, methods, and descriptors without
    running them; a name only ``__getattr__`` provides is looked up for real,
    and so is a ``__slots__`` entry, which exists on the class even when the
    instance never set it. With ``arity`` the member must also be callable
    with that many positional arguments.
    """
    static = inspect.getattr_static(obj, name, _MISSING)
    if static is _MISSING or isinstance(static, types.MemberDescriptorType):
        try:
            getattr(obj, name)
        except JobTimeout:
            raise
        except BaseException:
            return {"present": False}
    info: dict[str, Any] = {"present": True, "where": _member_where(obj, name, static)}
    if arity is None:
        return info
    try:
        value = getattr(obj, name)
    except JobTimeout:
        raise
    except BaseException as exc:
        info["callable"] = False
        info["error"] = _describe_exception(exc)
        return info
    info["callable"] = callable(value)
    if callable(value):
        info["bindable"] = _accepts_positional(value, arity)
    return info


def _inspect_class(
    index: int,
    case: dict[str, Any],
    request: dict[str, Any],
    module: Any,
    package: str | None,
) -> dict[str, Any]:
    """Report the run-time shape of a class and, optionally, of an instance.

    ``observe.construct`` (default true) builds an instance from the case's
    arguments; ``observe.names`` lists members to look up on it and
    ``observe.callables`` maps method names to the number of positional
    arguments they must accept. Whether the class is abstract is always
    reported, as Python itself decides it, external bases included.
    """
    observe = request.get("observe") or {}
    namespace = vars(module)
    outcome: dict[str, Any] = {"index": index, "status": "passed", "failures": []}
    _SPY_CALLS.clear()
    try:
        cls = _resolve_name(str(request["qualname"]), namespace, package)
        if not isinstance(cls, type):
            raise CaseSetupError(f"{request['qualname']!r} is not a class")
        args = [_build_value(v, namespace, package) for v in case.get("args", [])]
        kwargs = {
            k: _build_value(v, namespace, package)
            for k, v in (case.get("kwargs") or {}).items()
        }
    except CaseSetupError as exc:
        outcome["status"] = "error"
        outcome["failures"].append(f"setup: {exc}")
        return outcome
    outcome["abstract"] = bool(inspect.isabstract(cls))
    outcome["abstract_methods"] = sorted(getattr(cls, "__abstractmethods__", ()))
    if observe.get("singleton") is not None:
        outcome["singleton"] = _check_singleton(cls, observe["singleton"], args, kwargs)
        return outcome
    if not observe.get("construct", True):
        return outcome
    try:
        obj = cls(*args, **kwargs)
    except JobTimeout:
        raise
    except BaseException as exc:
        outcome["constructed"] = False
        outcome["raised"] = _describe_exception(exc)
        return outcome
    outcome["constructed"] = True
    try:
        _run_steps(obj, list(case.get("steps") or []), namespace, package)
    except CaseSetupError as exc:
        outcome["status"] = "error"
        outcome["failures"].append(f"setup: {exc}")
        return outcome
    _SPY_CALLS.clear()
    members: dict[str, Any] = {}
    for name in observe.get("names") or []:
        members[str(name)] = _describe_member(obj, str(name), None)
    for name, arity in (observe.get("callables") or {}).items():
        members[str(name)] = _describe_member(obj, str(name), int(arity))
    for name, class_name in (observe.get("types") or {}).items():
        member = members.setdefault(str(name), _describe_member(obj, str(name), None))
        if member.get("present"):
            member.update(
                _member_type(obj, str(name), str(class_name), namespace, package)
            )
    outcome["members"] = members
    if observe.get("observer"):
        outcome["observer"] = _check_observer(
            obj, observe["observer"], namespace, package
        )
    return outcome


def _check_singleton(
    cls: type, spec: dict[str, Any], args: list[Any], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Obtain the instance twice, through ``spec["access"]`` or the constructor.

    ``access`` names a class or static method of ``cls`` or, failing that, a
    function of its module (``get_config()``).
    """
    access = spec.get("access")
    result: dict[str, Any] = {"access": access or "constructor"}
    try:
        obtain = cls
        if access:
            module = sys.modules.get(cls.__module__)
            obtain = getattr(cls, str(access), None) or getattr(module, str(access))
        first = obtain(*args, **kwargs)
        second = obtain(*args, **kwargs)
    except JobTimeout:
        raise
    except BaseException as exc:
        result["error"] = _describe_exception(exc)
        return result
    result["same"] = first is second
    result["type"] = type(first).__qualname__
    return result


def _check_observer(
    obj: Any, spec: dict[str, Any], namespace: dict[str, Any], package: str | None
) -> dict[str, Any]:
    """Subscribe a spy listener, notify, and optionally unsubscribe and notify again."""
    listener = _Spy("listener")
    result: dict[str, Any] = {}

    def notify() -> int:
        before = len(_SPY_CALLS)
        getattr(obj, str(spec["notify"]))(*notify_args)
        return sum(1 for call in _SPY_CALLS[before:] if call["spy"] == "listener")

    try:
        notify_args = [
            _build_value(value, namespace, package)
            for value in spec.get("notify_args") or []
        ]
        # A keyed observer takes the event first: subscribe("created", fn).
        subscribe_args = [
            _build_value(value, namespace, package)
            for value in spec.get("subscribe_args") or []
        ]
        getattr(obj, str(spec["subscribe"]))(*subscribe_args, listener)
        result["notified"] = notify()
        if spec.get("unsubscribe"):
            getattr(obj, str(spec["unsubscribe"]))(*subscribe_args, listener)
            result["after_unsubscribe"] = notify()
    except JobTimeout:
        raise
    except BaseException as exc:
        result["error"] = _describe_exception(exc)
    return result


def _run_steps(
    subject: Any,
    steps: list[dict[str, Any]],
    namespace: dict[str, Any],
    package: str | None,
) -> None:
    """Call ``steps`` (other methods of ``subject``) to prepare its state.

    A step that cannot run means the case could not be set up, like an
    argument that cannot be built.
    """
    for number, step in enumerate(steps):
        name = str(step.get("call"))
        try:
            args = [_build_value(v, namespace, package) for v in step.get("args", [])]
            kwargs = {
                k: _build_value(v, namespace, package)
                for k, v in (step.get("kwargs") or {}).items()
            }
            _run_to_completion(getattr(subject, name)(*args, **kwargs))
        except (JobTimeout, CaseSetupError):
            raise
        except BaseException as exc:
            raise CaseSetupError(
                f"step {number} ({name}) raised {_describe_exception(exc)}"
            ) from exc


_DRAIN_LIMIT = 10_000  # items taken from a generator the target returns


def _run_to_completion(result: Any) -> None:
    """Run the body of a coroutine or generator the target's call returned.

    Calling an ``async def`` or generator function only creates the object;
    without this, its body would never run and nothing would be observed.
    A generator is drained up to ``_DRAIN_LIMIT`` items, so an endless one
    ends instead of running into the timeout.
    """
    if inspect.iscoroutine(result):
        import asyncio  # only targets that use it pay for importing it

        asyncio.run(result)
    elif inspect.isasyncgen(result):
        import asyncio

        async def drain() -> None:
            taken = 0
            async for _ in result:
                taken += 1
                if taken >= _DRAIN_LIMIT:
                    break
            await result.aclose()

        asyncio.run(drain())
    elif inspect.isgenerator(result):
        for _ in itertools.islice(result, _DRAIN_LIMIT):
            pass
        result.close()


@contextlib.contextmanager
def _case_stdin(case: dict[str, Any]) -> Iterator[None]:
    """Give the target the case's ``stdin`` text as its keyboard while it runs.

    ``input()`` and ``sys.stdin`` read that text; what the case leaves unread
    is dropped, and reading past its end raises ``EOFError``. The original
    ``sys.stdin`` comes back afterwards, so the text never reaches another
    case. A case without ``stdin`` keeps the probe's own, already exhausted,
    stdin.
    """
    if "stdin" not in case:
        yield
        return
    original = sys.stdin
    sys.stdin = io.StringIO(str(case["stdin"]))
    try:
        yield
    finally:
        sys.stdin = original


def _run_case(
    index: int,
    case: dict[str, Any],
    request: dict[str, Any],
    module: Any,
    package: str | None,
    writes: WriteRecorder | None = None,
    instances: InstanceRecorder | None = None,
) -> dict[str, Any]:
    """Run one case with its ``stdin``; see :func:`_observe_case`."""
    with _case_stdin(case):
        return _observe_case(index, case, request, module, package, writes, instances)


def _observe_case(
    index: int,
    case: dict[str, Any],
    request: dict[str, Any],
    module: Any,
    package: str | None,
    writes: WriteRecorder | None = None,
    instances: InstanceRecorder | None = None,
) -> dict[str, Any]:
    """Call the target once with the case's arguments and report what it did.

    Cases carry call arguments only. What the probe reports is structural:
    the calls the target's module made into other modules (``observe.calls``),
    or, with ``observe.calls == "edges"``, every call between two project
    modules (and, with ``observe.external``, every call from project code
    into a library); attribute assignments from outside the owning class
    (``observe.writes``); project classes instantiated by project code
    (``observe.instances``, including while a method's instance is built);
    and, for runtime ``enforce_flow``, the order of flow stages. Outside flow
    tracing, the lines of the target's own code the call ran and missed are
    reported too (``lines``), so a pass can say what was not checked. Threads
    the target starts are followed. An exception the call raises is
    reported, not judged.
    """
    _reset_random()
    if request.get("kind") == "class":
        return _inspect_class(index, case, request, module, package)
    _SPY_CALLS.clear()
    observe = request.get("observe") or {}
    if instances is not None and observe.get("instances"):
        transitive = observe.get("instances") == "transitive"
        instances.start(module.__name__ if transitive else None)
    namespace = vars(module)
    qualname: str = request["qualname"]
    owner_name, _, member_name = qualname.rpartition(".")
    outcome: dict[str, Any] = {"index": index, "status": "passed", "failures": []}
    failures: list[str] = outcome["failures"]

    try:
        owner = (
            _resolve_name(owner_name, namespace, package)
            if request["kind"] == "method"
            else None
        )
        if owner is not None and isinstance(
            inspect.getattr_static(owner, member_name, None),
            (staticmethod, classmethod),
        ):
            # Static and class methods need no instance; building one would
            # demand constructor arguments the call never uses.
            subject = None
            func = getattr(owner, member_name)
        elif owner is not None:
            init = case.get("init", request.get("init")) or {}
            init_args = [
                _build_value(v, namespace, package) for v in init.get("args", [])
            ]
            init_kwargs = {
                k: _build_value(v, namespace, package)
                for k, v in (init.get("kwargs") or {}).items()
            }
            try:
                subject = owner(*init_args, **init_kwargs)
            except JobTimeout:
                raise
            except BaseException as exc:
                raise CaseSetupError(
                    f"constructing {owner_name!r} raised {_describe_exception(exc)}"
                ) from exc
            func = getattr(subject, member_name)
        else:
            subject = None
            func = _resolve_name(qualname, namespace, package)
        if case.get("steps"):
            if subject is None:
                raise CaseSetupError("steps need an instance to call methods on")
            # The steps prepare the instance; what they do is not observed.
            recording = instances is not None and instances.active
            if instances is not None:
                instances.active = False
            _run_steps(subject, list(case["steps"]), namespace, package)
            if instances is not None:
                instances.active = recording
            _SPY_CALLS.clear()
        args = [_build_value(v, namespace, package) for v in case.get("args", [])]
        kwargs = {
            k: _build_value(v, namespace, package)
            for k, v in (case.get("kwargs") or {}).items()
        }
        if instances is not None and instances.active:
            # Building the arguments may have imported more of the project.
            instances.wrap_loaded()
    except CaseSetupError as exc:
        if instances is not None:
            instances.stop()
        outcome["status"] = "error"
        failures.append(f"setup: {exc}")
        return outcome

    # Internal keys used by the runtime enforce_flow check: "capture_stages"
    # runs the reference and reports the project calls each flow stage makes;
    # "flow_calls" runs the target and reports every project call in order.
    capture = case.get("capture_stages")
    flow_calls = bool(case.get("flow_calls"))
    stages: list[list[Any]] = []
    called: list[dict[str, str]] = []
    calls: CallRecorder | None = None
    root = request.get("target_root")
    project = _Project(str(root), package) if root else None
    if observe.get("calls") == "edges":
        calls = CallRecorder(
            None, package, project, external=bool(observe.get("external"))
        )
    elif observe.get("calls") == "transitive":
        calls = CallRecorder(module.__name__, package, project, transitive=True)
    elif observe.get("calls"):
        # The project only names the file of each call here.
        calls = CallRecorder(module.__name__, package, project)
    tracing = bool(capture or flow_calls)
    if tracing and project is None:
        project = _Project(os.path.dirname(str(module.__file__)), package)
    # Flow tracing installs its own trace function; line coverage needs one too.
    lines = LineRecorder(func, project) if project is not None and not tracing else None
    watch_writes = writes is not None and bool(observe.get("writes"))
    if writes is not None and watch_writes:
        writes.start([subject, *args, *kwargs.values()])
    try:
        with (
            calls.watching() if calls else contextlib.nullcontext(),
            lines.watching() if lines else contextlib.nullcontext(),
            (
                writes.watching()
                if writes is not None and watch_writes
                else contextlib.nullcontext()
            ),
            _joining_new_threads(),
        ):
            if tracing and project is not None:
                _call_with_trace(
                    func,
                    args,
                    kwargs,
                    project,
                    capture["spans"] if capture else None,
                    stages if capture else None,
                    called if flow_calls else None,
                )
            else:
                _run_to_completion(func(*args, **kwargs))
    except CaseSetupError as exc:
        outcome["status"] = "error"
        failures.append(f"setup: {exc}")
        return outcome
    except JobTimeout:
        raise
    except BaseException as exc:  # SystemExit included: report, do not die
        outcome["raised"] = _describe_exception(exc)
        if capture:
            # The reference has to finish to say what its stages are.
            failures.append(f"unexpected {outcome['raised']}")
            outcome["traceback"] = traceback.format_exc(limit=-3)
    finally:
        if writes is not None:
            writes.active = False
        if instances is not None:
            instances.stop()

    coverage = lines.report() if lines is not None else None
    if coverage is not None:
        outcome["lines"] = coverage
    if calls is not None:
        outcome["calls"] = calls.calls
    if writes is not None and observe.get("writes"):
        outcome["writes"] = list(writes.writes)
    if instances is not None and observe.get("instances"):
        outcome["instances"] = list(instances.instances)
    if observe.get("spies"):
        outcome["spy_calls"] = list(_SPY_CALLS)

    if capture:
        outcome["stages"] = stages
    if flow_calls:
        outcome["flow_calls"] = called

    if failures:
        outcome["status"] = "failed"
    return outcome


class _Captured(io.StringIO):
    """A job's output buffer; target code that closes ``sys.stdout`` keeps it."""

    def close(self) -> None:
        pass


_RETRIGGER_S = 0.1
_STDERR_TAIL = 2000


@contextlib.contextmanager
def _job_deadline(seconds: float) -> Iterator[dict[str, bool]]:
    """Interrupt the job after ``seconds`` where an interval timer exists.

    Yields a state dict whose ``"fired"`` entry turns true once the deadline
    passed. The timer keeps re-firing every 0.1 s until the job ends, because a
    bare ``except:`` in target code can swallow one ``JobTimeout``; the caller
    treats a fired deadline as a timeout even if the job then returned
    normally. Without ``signal.setitimer`` (Windows) only the whole batch is
    bounded, by the runner's timeout.
    """
    state = {"fired": False}
    if not hasattr(signal, "setitimer"):
        yield state
        return

    def on_alarm(_signum: int, _frame: Any) -> None:
        state["fired"] = True
        raise JobTimeout()

    previous = signal.signal(signal.SIGALRM, on_alarm)
    if seconds <= 0:
        state["fired"] = True
    else:
        signal.setitimer(signal.ITIMER_REAL, seconds, _RETRIGGER_S)
    try:
        yield state
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _run_job(
    job: dict[str, Any],
    module: Any,
    package: str | None,
    writes: WriteRecorder,
    *,
    already_spent_s: float = 0.0,
    instances: InstanceRecorder | None = None,
) -> dict[str, Any]:
    """Run the cases of one rule; a batch holds several jobs for one module.

    ``already_spent_s`` is the time the probe needed to start and import the
    module. It is charged to every job, so a job gets the same budget as the
    rule would get in an interpreter of its own, where ``timeout_s`` covers
    start-up and import too. The job's own output is captured separately so it
    is reported with this rule only.
    """
    timeout_s = float(job.get("timeout_s", 5.0))
    cases: list[dict[str, Any]] = []
    captured = _Captured()
    timed_out = False
    # A late interrupt can land before a case puts its stdin back.
    stdin = sys.stdin
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        # The re-firing timer can interrupt anywhere until the deadline context
        # has disarmed it, including inside the inner handler; the outer
        # handler catches such a late interrupt.
        try:
            with _job_deadline(timeout_s - already_spent_s) as deadline:
                try:
                    if deadline["fired"]:
                        raise JobTimeout()
                    for index, case in enumerate(job["cases"]):
                        cases.append(
                            _run_case(
                                index,
                                case,
                                job,
                                module,
                                package,
                                writes,
                                instances,
                            )
                        )
                except JobTimeout:
                    timed_out = True
                timed_out = timed_out or deadline["fired"]
        except JobTimeout:
            timed_out = True
    sys.stdin = stdin
    result: dict[str, Any] = {
        "status": "timeout" if timed_out else "completed",
        "cases": cases,
        "stderr": captured.getvalue()[-_STDERR_TAIL:],
    }
    if timed_out:
        result["error"] = f"target did not finish within {timeout_s:g} s"
    return result


def _reset_random() -> None:
    """Seed ``random`` alike before importing the target and before every case.

    Code that shuffles or samples then makes the same calls in every run, and
    each case starts from the same state whatever ran before it.
    """
    random.seed(0)


def _import_target(request: dict[str, Any]) -> tuple[Any, str | None]:
    _reset_random()
    root = request["target_root"]
    package = request.get("package")
    sys.path.insert(0, os.path.dirname(root) if package else root)
    module_path = request["module_path"]
    if package:
        if request.get("mode") == "imports" and module_path:
            module = _import_without_parents(root, package, module_path)
            if module is not None:
                return module, package
        module_path = f"{package}.{module_path}" if module_path else package
    return importlib.import_module(module_path), package


def _import_without_parents(root: str, package: str, module_path: str) -> Any:
    """The target module, its enclosing packages' ``__init__.py`` not run.

    A package that re-exports its application (``from .wiring import serve``)
    imports every adapter as soon as any submodule is loaded; those imports
    are the package's, not the module's. The enclosing packages are stand-ins
    with the right ``__path__``; what the module imports itself, including
    other packages of the project, loads as usual. A module that needs its
    package's own names cannot load so; ``None`` then, and the caller
    imports it the ordinary way.
    """
    parts = [package, *module_path.split(".")[:-1]]
    for depth in range(1, len(parts) + 1):
        name = ".".join(parts[:depth])
        if name in sys.modules:
            continue
        stand_in = types.ModuleType(name)
        stand_in.__path__ = [os.path.join(root, *parts[1:depth])]
        stand_in.__package__ = name
        sys.modules[name] = stand_in
    try:
        return importlib.import_module(f"{package}.{module_path}")
    except Exception:  # noqa: BLE001 - any failure: fall back to a plain import
        for name in list(sys.modules):
            if name == package or name.startswith(f"{package}."):
                del sys.modules[name]
        return None


def main() -> int:
    started = time.monotonic()
    # Running this file puts its own directory first on sys.path; drop it so a
    # target module named like a file next to this script (``runner``) still
    # resolves to the target. Standard-library modules this script has already
    # imported (``json``, ``os``, ...) stay cached and cannot be targets.
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != here]

    request = json.loads(sys.stdin.read())
    recorder = ImportRecorder(request["target_root"])
    recorder.install()
    real_stdout = sys.stdout
    response: dict[str, Any]
    with contextlib.redirect_stdout(sys.stderr):
        try:
            module, package = _import_target(request)
        except BaseException as exc:
            response = {
                "status": "import_error",
                "error": _describe_exception(exc),
                "traceback": traceback.format_exc(limit=-3),
                "cases": [],
            }
        else:
            recorder.phase = "run"
            writes = WriteRecorder(request["target_root"], package)
            instances = InstanceRecorder(request["target_root"], package)
            if request.get("mode") == "imports":
                hits = recorder.forbidden_hits(
                    list(request.get("forbidden") or []),
                    list(request.get("allow") or []),
                    {"import"},
                    package,
                )
                response = {"status": "completed", "cases": [], "imports": hits}
            elif "jobs" in request:
                # Start-up and import, measured once: every job is charged
                # this, never the time the jobs before it took.
                startup_s = time.monotonic() - started
                response = {
                    "status": "completed",
                    "cases": [],
                    "jobs": {
                        str(job["id"]): _run_job(
                            {**job, "target_root": request["target_root"]},
                            module,
                            package,
                            writes,
                            already_spent_s=startup_s,
                            instances=instances,
                        )
                        for job in request["jobs"]
                    },
                }
            else:
                cases = [
                    _run_case(index, case, request, module, package, writes, instances)
                    for index, case in enumerate(request["cases"])
                ]
                response = {"status": "completed", "cases": cases}
    real_stdout.write(json.dumps(response))
    real_stdout.flush()
    return 0


_PR_SET_CHILD_SUBREAPER = 36
_REAP_ROUNDS = 20


def _become_subreaper() -> None:
    """Keep processes the target detaches (``setsid``, double fork) our own.

    Orphans would otherwise be adopted by init, out of reach of the runner,
    which only kills the probe's process group. Linux only.
    """
    if not sys.platform.startswith("linux"):
        return
    try:
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl(_PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)
    except (OSError, AttributeError):
        pass


def _kill_descendants() -> None:
    """End every process the target started that still runs.

    As a subreaper the probe inherits the children of every process it kills,
    so the loop goes on until none is left.
    """
    if not os.path.isdir("/proc"):
        return
    me = os.getpid()
    for _ in range(_REAP_ROUNDS):
        children = []
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                with open(
                    f"/proc/{entry}/stat", encoding="ascii", errors="replace"
                ) as f:
                    stat = f.read()
            except OSError:
                continue
            # "pid (comm) state ppid ...": comm may contain spaces or ")".
            fields = stat.rpartition(")")[2].split()
            if len(fields) > 1 and fields[1] == str(me):
                children.append(int(entry))
        if not children:
            return
        for pid in children:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        for pid in children:
            try:
                os.waitpid(pid, 0)
            except OSError:
                pass


if __name__ == "__main__":
    _become_subreaper()
    exit_code = main()
    _kill_descendants()
    sys.stdout.flush()
    sys.stderr.flush()
    # The response is written; a non-daemon thread the target left running
    # would otherwise keep the interpreter alive until the runner's timeout,
    # which then discards the finished response.
    os._exit(exit_code)
