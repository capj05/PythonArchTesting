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
import enum
import importlib
import importlib.util
import inspect
import io
import json
import os
import signal
import sys
import threading
import time
import traceback
import types
from typing import Any, Iterator

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
        value = getattr(value, part, _MISSING)
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
    records its call. A call returns its first positional argument (or None),
    so a strategy or decorator chain that passes a value through keeps running.
    """

    def __init__(self, name: str) -> None:
        object.__setattr__(self, "_spy_name", name)

    def _record(
        self, member: str, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> Any:
        if len(_SPY_CALLS) >= _SPY_CALL_LIMIT:
            return args[0] if args else None
        _SPY_CALLS.append(
            {
                "spy": object.__getattribute__(self, "_spy_name"),
                "member": member,
                "args": len(args) + len(kwargs),
            }
        )
        return args[0] if args else None

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


def _build_value(value: Any, namespace: dict[str, Any], package: str | None) -> Any:
    if isinstance(value, dict) and "$spy" in value:
        return _Spy(str(value["$spy"]))
    if isinstance(value, dict) and "$new" in value:
        factory = _resolve_name(str(value["$new"]), namespace, package)
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
    """

    def __init__(
        self,
        caller_module: str | None,
        package: str | None,
        project: _Project | None = None,
    ) -> None:
        self._caller = caller_module
        self._package = package
        self._project = project
        self.calls: list[dict[str, Any]] = []
        self._seen: set[tuple[str, str, str, int]] = set()

    def _note(self, caller: Any, module: str | None, callee: str) -> None:
        source = _module_of(caller)
        if not module or module == source:
            return
        key = (str(source), module, callee, caller.f_lineno)
        if key in self._seen:
            return
        self._seen.add(key)
        self.calls.append(
            {
                "from": _local_module(source, self._package),
                "module": _local_module(module, self._package),
                "callee": callee,
                "caller": _code_name(caller.f_code),
                "line": caller.f_lineno,
            }
        )

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
                if self._in_project(caller) and self._in_project(frame):
                    self._note(caller, _module_of(frame), _code_name(frame.f_code))
            elif _module_of(caller) == self._caller:
                self._note(caller, _module_of(frame), _code_name(frame.f_code))
        elif (
            event == "c_call"
            and self._caller is not None
            and _module_of(frame) == self._caller
        ):
            owner = getattr(arg, "__self__", None)
            module = getattr(arg, "__module__", None)
            if not module and owner is not None:
                # Methods of C types (``cursor.execute``) carry no __module__.
                module = getattr(type(owner), "__module__", None)
            name = getattr(arg, "__name__", None)
            if module == "builtins" or (name and getattr(builtins, name, None) is arg):
                # len(), print(), list.append() belong to no layer; open() is
                # a builtin too, although it reports _io as its module.
                return
            if module and module.startswith("_") and module[1:] in sys.modules:
                # pickle.dumps is _pickle.dumps; report the public module.
                module = module[1:]
            self._note(frame, module, str(getattr(arg, "__qualname__", arg)))

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
    """

    _MARK = "__pat_write_recorder__"

    def __init__(self, target_root: str, package: str | None = None) -> None:
        self._project = _Project(target_root, package)
        self._package = package
        self.active = False
        self.writes: list[dict[str, Any]] = []
        self._seen: set[tuple[str, str, str, int]] = set()
        self._method_codes: dict[type, set[Any]] = {}

    def start(self) -> None:
        """Begin recording one case, wrapping classes imported since the last."""
        self.install()
        self.writes = []
        self._seen = set()
        self.active = True

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
            }
        )


class InstanceRecorder:
    """Record which project code creates instances of the project's classes.

    Every class defined under the target root gets an ``__init__`` wrapper
    that, while ``active`` is set, notes the object's class and the frame that
    asked for it. Only the outermost constructor of an object counts, so a
    ``super().__init__()`` chain is one instantiation of the most derived class.
    Objects created by code outside the target root (the probe building case
    arguments, the standard library) are ignored.
    """

    _MARK = "__pat_instance_recorder__"

    def __init__(self, target_root: str, package: str | None = None) -> None:
        self._project = _Project(target_root, package)
        self._package = package
        self.active = False
        self.instances: list[dict[str, Any]] = []
        self._seen: set[tuple[str, str, int]] = set()
        self._building: set[int] = set()

    def start(self) -> None:
        """Begin recording one case, wrapping classes imported since the last."""
        for cls in self._project.classes():
            klass: Any = cls  # the unbound constructor, which mypy reads as bound
            if not getattr(klass.__init__, self._MARK, False):
                self._wrap(cls)
        self.instances = []
        self._seen = set()
        self.active = True

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
        self.instances.append(
            {
                "class": cls.__qualname__,
                "module": _local_module(cls.__module__, self._package),
                "from": source,
                "creator": f"{source}:{_code_name(frame.f_code)}",
                "file": relpath,
                "line": frame.f_lineno,
            }
        )


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
            return original_import(name, globals, locals, fromlist, level)

        def hooked_import_module(name: str, package: str | None = None) -> Any:
            level = len(name) - len(name.lstrip("."))
            self._note(name.lstrip("."), sys._getframe(1), package, level, ())
            return original_import_module(name, package)

        builtins.__import__ = hooked_import
        # importlib.__import__ is a separate function with the same contract.
        importlib.__import__ = hooked_import
        importlib.import_module = hooked_import_module

    def forbidden_hits(
        self, forbidden: list[str], allow: list[str], phases: set[str]
    ) -> list[dict[str, Any]]:
        def matches(module_name: str, prefix: str) -> bool:
            return module_name == prefix or module_name.startswith(prefix + ".")

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
    members: dict[str, Any] = {}
    for name in observe.get("names") or []:
        members[str(name)] = _describe_member(obj, str(name), None)
    for name, arity in (observe.get("callables") or {}).items():
        members[str(name)] = _describe_member(obj, str(name), int(arity))
    outcome["members"] = members
    if observe.get("observer"):
        outcome["observer"] = _check_observer(
            obj, observe["observer"], namespace, package
        )
    return outcome


def _check_singleton(
    cls: type, spec: dict[str, Any], args: list[Any], kwargs: dict[str, Any]
) -> dict[str, Any]:
    """Obtain the instance twice, through ``spec["access"]`` or the constructor."""
    access = spec.get("access")
    result: dict[str, Any] = {"access": access or "constructor"}
    try:
        obtain = getattr(cls, str(access)) if access else cls
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
        getattr(obj, str(spec["subscribe"]))(listener)
        result["notified"] = notify()
        if spec.get("unsubscribe"):
            getattr(obj, str(spec["unsubscribe"]))(listener)
            result["after_unsubscribe"] = notify()
    except JobTimeout:
        raise
    except BaseException as exc:
        result["error"] = _describe_exception(exc)
    return result


def _run_case(
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
    modules; attribute assignments from outside the owning class
    (``observe.writes``); project classes instantiated by project code
    (``observe.instances``, including while a method's instance is built);
    and, for runtime ``enforce_flow``, the order of flow stages. Outside flow
    tracing, the lines of the target's own code the call ran and missed are
    reported too (``lines``), so a pass can say what was not checked. Threads
    the target starts are followed. An exception the call raises is
    reported, not judged.
    """
    if request.get("kind") == "class":
        return _inspect_class(index, case, request, module, package)
    _SPY_CALLS.clear()
    observe = request.get("observe") or {}
    if instances is not None and observe.get("instances"):
        instances.start()
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
        args = [_build_value(v, namespace, package) for v in case.get("args", [])]
        kwargs = {
            k: _build_value(v, namespace, package)
            for k, v in (case.get("kwargs") or {}).items()
        }
    except CaseSetupError as exc:
        if instances is not None:
            instances.active = False
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
        calls = CallRecorder(None, package, project)
    elif observe.get("calls"):
        calls = CallRecorder(module.__name__, package)
    tracing = bool(capture or flow_calls)
    if tracing and project is None:
        project = _Project(os.path.dirname(str(module.__file__)), package)
    # Flow tracing installs its own trace function; line coverage needs one too.
    lines = LineRecorder(func, project) if project is not None and not tracing else None
    if writes is not None and observe.get("writes"):
        writes.start()
    try:
        with (
            calls.watching() if calls else contextlib.nullcontext(),
            lines.watching() if lines else contextlib.nullcontext(),
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
                func(*args, **kwargs)
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
            instances.active = False

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
    result: dict[str, Any] = {
        "status": "timeout" if timed_out else "completed",
        "cases": cases,
        "stderr": captured.getvalue()[-_STDERR_TAIL:],
    }
    if timed_out:
        result["error"] = f"target did not finish within {timeout_s:g} s"
    return result


def _import_target(request: dict[str, Any]) -> tuple[Any, str | None]:
    root = request["target_root"]
    package = request.get("package")
    sys.path.insert(0, os.path.dirname(root) if package else root)
    module_path = request["module_path"]
    if package:
        module_path = f"{package}.{module_path}" if module_path else package
    return importlib.import_module(module_path), package


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
