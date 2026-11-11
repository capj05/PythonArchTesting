"""Named architectural mutation operators.

Each operator seeds one kind of architectural violation into a copy of a
project, deterministically, so a marker can be checked against it: a marker
that states an intent must fail on every mutant that breaks that intent and
pass on the project itself. The operators generalise the hand-written
mutants of ``example/architectural_mutants``:

- ``add_import``: a module imports a project module it did not import (a
  layer bypass, or a cycle when the other module imports it back);
- ``lazy_import``: the same import, inside the module's first function;
- ``add_library``: a module imports a library (``pickle`` by default), a
  forbidden technology;
- ``rebuild_injected``: a constructor builds its own collaborator of the
  injected one's class instead of keeping the one it was given (broken
  dependency injection);
- ``drop_call``: a method no longer calls a collaborator it holds
  (``self.repo.save(...)``), a skipped step;
- ``use_private_name``: another module gets a private helper
  (``_archtest_private``), and a module imports and calls it, past that
  module's interface (two files change);
- ``break_port``: a public method of a class takes a new required parameter,
  or is renamed, so the class no longer satisfies a port it implements;
- ``foreign_write``: a method or a module-level function assigns a data
  attribute (preferably a private one) of an object it got from outside
  (``order._total = order._total``), where it changes that object's state;
- ``add_io_call``: a function or method talks to the user or a file first
  thing: ``print(...)``, ``input()`` or ``open(...)`` (the call is ``member``);
- ``mutate_private_container``: right after a function first calls a method
  of an object of a project class it got as a parameter, it changes the
  contents of that object's first private container (``obj._x["k"] = 0``,
  ``obj._x.append(0)``, ``obj._x.add(0)``); the container is what the
  class's ``__init__`` assigns ``{}``, ``[]``, ``set()``, ``dict(...)``,
  ``list(...)``, ``defaultdict(...)``, ``Counter(...)``, ``OrderedDict(...)``,
  a comprehension or a choice with such a branch (``x or {}``), or a
  ``@dataclass`` field's ``default_factory``, and nothing else ever; a
  name-mangled ``__x`` is written as ``obj._Owner__x``;
- ``mutate_public_container``: the same with a public container;
- ``stub_role_call``: a function or method no longer calls the functions of
  one project module (``member``): each call's function becomes
  ``(lambda *a, **k: None)``;
- ``add_io_via_helper``: a new module ``_archtest_helper`` prints in
  ``say``, and a function or method imports and calls it first thing, on
  one line (two files change);
- ``read_private_attribute``: a function first reads the first private data
  attribute of an object of a project class it got as a parameter
  (``_ = obj._x``; a name-mangled ``__x`` as ``obj._Owner__x``, as code
  outside the class must spell it), or reads it of an object a module global
  holds right after its first use;
- ``add_builtin_call``: ``add_io_call`` generalised to any builtin call an
  error can name: the three I/O calls, ``isinstance(None, (object,)[0])``
  and ``type((None,)[0]) == object``, a branch on the type (the call is ``member``);
  ``add_io_call`` stays its I/O-only form;
- ``drop_base``: a top-level class no longer names one of its bases
  (``class Square(Shape)`` becomes ``class Square``); one mutant per class
  and base, ``object`` excepted (the base is ``member``);
- ``concretize_base``: an abstract top-level class becomes an ordinary one:
  ``ABC``, ``Protocol`` and ``metaclass=ABCMeta`` leave its bases and
  ``@abstractmethod`` its methods; the import of ``abc`` stays;
- ``hardcode_collaborator``: a constructor builds a collaborator of its own
  instead of keeping the one it was given: ``self.x = x`` becomes
  ``self.x = C()``, ``C`` the first class by name (of the modules given as
  ``instantiable``) that can be built without arguments and is not
  abstract; the import follows the module's own imports (the class is
  ``member``). Unlike ``rebuild_injected`` it works when the collaborator
  given is a spy, which cannot be rebuilt from its class.

A mutant is a whole new text of one file; nothing is written here. The
operators live in ``mutation.ops``; ``REGISTRY`` names each one, and
``generate_mutants`` runs them in that order.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

from pythonarchtesting.mutation.class_model import class_index
from pythonarchtesting.mutation.objects import global_owners
from pythonarchtesting.mutation.ops.attributes import (
    foreign_write,
    mutate_container,
    read_private_attribute,
)
from pythonarchtesting.mutation.ops.calls import drop_call, stub_role_call
from pythonarchtesting.mutation.ops.classes import (
    break_port,
    concretize_base,
    drop_base,
)
from pythonarchtesting.mutation.ops.imports import (
    add_import,
    add_library,
    dynamic_import,
    use_private_name,
)
from pythonarchtesting.mutation.ops.injection import (
    hardcode_collaborator,
    rebuild_injected,
)
from pythonarchtesting.mutation.ops.io import (
    BUILTIN_CALLS,
    IO_CALLS,
    add_io_call,
    add_io_via_helper,
)
from pythonarchtesting.mutation.project import (
    Change,
    Module,
    Mutant,
    ParameterClasses,
    Spied,
    load_modules,
)
from pythonarchtesting.mutation.syntax import Syntax, parses

DEFAULT_LIBRARIES = ("pickle",)


@dataclass
class OperatorInput:
    """What one ``generate_mutants`` call gives its operators: the project's
    modules, the name absolute imports reach it by (``package``) and the
    options. ``classes`` and ``owners`` are worked out once, when an
    operator first needs them, and shared by the operators that do."""

    modules: list[Module]
    package: str
    libraries: Sequence[str]
    parameter_classes: Optional[ParameterClasses]
    instantiable: Optional[Sequence[str]]
    spied: Optional[Spied]

    @cached_property
    def classes(self) -> dict[str, list[ast.ClassDef]]:
        """The project's top-level classes by name (``class_index``)."""
        return class_index(self.modules)

    @cached_property
    def owners(self) -> dict[str, dict[str, ast.ClassDef]]:
        """The objects module globals hold, per file (``global_owners``)."""
        return global_owners(self.modules, self.classes, self.package)


# Each operator by name, in the order ``generate_mutants`` runs them: a
# mutant's id counts the mutants before it, so the order is part of the ids.
REGISTRY: dict[str, Callable[[OperatorInput], Iterable[Change]]] = {
    "add_import": lambda run: add_import(run.modules, lazy=False),
    "lazy_import": lambda run: add_import(run.modules, lazy=True),
    "add_library": lambda run: add_library(run.modules, run.libraries),
    "dynamic_import": lambda run: dynamic_import(run.modules, run.libraries),
    "rebuild_injected": lambda run: rebuild_injected(run.modules),
    "drop_call": lambda run: drop_call(run.modules),
    "use_private_name": lambda run: use_private_name(run.modules),
    "break_port": lambda run: break_port(run.modules),
    "foreign_write": lambda run: foreign_write(
        run.modules, run.classes, run.owners, run.parameter_classes
    ),
    "add_io_call": lambda run: add_io_call(run.modules),
    "mutate_private_container": lambda run: mutate_container(
        run.modules, run.classes, run.owners, True, run.parameter_classes
    ),
    "mutate_public_container": lambda run: mutate_container(
        run.modules, run.classes, run.owners, False, run.parameter_classes
    ),
    "stub_role_call": lambda run: stub_role_call(run.modules, run.package),
    "add_io_via_helper": lambda run: add_io_via_helper(run.modules),
    "read_private_attribute": lambda run: read_private_attribute(
        run.modules, run.classes, run.owners, run.parameter_classes
    ),
    "add_builtin_call": lambda run: add_io_call(run.modules, BUILTIN_CALLS),
    "drop_base": lambda run: drop_base(run.modules),
    "concretize_base": lambda run: concretize_base(run.modules),
    "hardcode_collaborator": lambda run: hardcode_collaborator(
        run.modules, run.instantiable, run.spied
    ),
}
OPERATORS = tuple(REGISTRY)


def generate_mutants(
    root: Path,
    operators: Optional[Iterable[str]] = None,
    *,
    libraries: Sequence[str] = DEFAULT_LIBRARIES,
    limit: Optional[int] = None,
    parameter_classes: Optional[ParameterClasses] = None,
    instantiable: Optional[Sequence[str]] = None,
    spied: Optional[Spied] = None,
    skipped: Optional[list[tuple[str, str]]] = None,
) -> list[Mutant]:
    """Every mutant the ``operators`` (all by default) make of the project at ``root``.

    The order is stable: by operator, then by file and position. ``limit``
    keeps the first that many. ``parameter_classes`` (from a task's cases)
    tells the operators that need an object of a project class which
    parameters hold one (``ParameterClasses``). ``instantiable`` names the
    modules (each with its submodules) or the classes (``module.Class``)
    ``hardcode_collaborator`` may build; every project module by default.
    ``spied`` limits ``hardcode_collaborator`` to the constructor parameters
    a task gives a spy (``Spied``); every kept parameter by default.
    ``skipped``, when given, gets ``(file, why)`` for each file left out
    because it does not decode or parse.
    """
    chosen = list(OPERATORS if operators is None else operators)
    unknown = sorted(set(chosen) - set(OPERATORS))
    if unknown:
        raise ValueError(
            f"unknown operator(s) {', '.join(unknown)}; use {', '.join(OPERATORS)}"
        )
    modules = load_modules(root, skipped)
    # The name absolute imports reach the project by (``game.world``).
    package = Path(root).name if (Path(root) / "__init__.py").is_file() else ""
    if limit is not None and limit == 0:
        return []
    run = OperatorInput(
        modules, package, libraries, parameter_classes, instantiable, spied
    )
    syntax = {module.file: Syntax(module) for module in modules}
    produced: list[Mutant] = []
    for operator in OPERATORS:
        if operator not in chosen:
            continue
        for change in REGISTRY[operator](run):
            # An operator never hands out code that does not parse.
            if not all(
                parses(text) if file not in syntax else syntax[file].parses(text)
                for file, text in ((change.file, change.source), *change.also)
            ):
                continue
            produced.append(
                Mutant(
                    id=f"{operator}-{len(produced) + 1:03d}",
                    operator=operator,
                    file=change.file,
                    description=change.description,
                    source=change.source,
                    subject=change.subject or change.file,
                    also=change.also,
                    imported=change.imported,
                    owner=change.owner,
                    collaborator=change.collaborator,
                    member=change.member,
                    line=change.line,
                    function=change.function,
                )
            )
            if limit is not None and len(produced) >= limit >= 0:
                return produced  # the first ``limit``: none after them counts
    return produced[:limit] if limit is not None else produced


__all__ = [
    "BUILTIN_CALLS",
    "DEFAULT_LIBRARIES",
    "IO_CALLS",
    "OPERATORS",
    "REGISTRY",
    "Mutant",
    "OperatorInput",
    "generate_mutants",
]
