"""Operators that add I/O or builtin calls: ``add_io_call``,
``add_builtin_call`` and ``add_io_via_helper``.
"""

from __future__ import annotations

import ast
from typing import Iterator, Mapping

from pythonarchtesting.mutation.functions import (
    class_methods,
    module_functions,
)
from pythonarchtesting.mutation.imports import relative
from pythonarchtesting.mutation.project import Change, Module
from pythonarchtesting.mutation.source_edit import function_insert, insert
from pythonarchtesting.util.ast_utils import never_runs

# The calls ``add_io_call`` inserts, by ``member``: each talks to the user or
# to a file and does nothing else (a missing file is no error).
IO_CALLS = {
    "print": ['print("archtest")'],
    "input": ["input()"],
    "open": [
        "try:",
        '    open("archtest-missing.txt", encoding="utf-8").close()',
        "except OSError:",
        "    pass",
    ],
}


# The calls ``add_builtin_call`` inserts, by ``member``: those of
# ``add_io_call`` and a test of an object's type, which does nothing either.
# Each is a type test as ``forbid_runtime_calls`` counts one: ``isinstance``
# against a class it cannot tell from a builtin one (computed at run time),
# ``type()`` whose result is compared.
BUILTIN_CALLS = {
    **IO_CALLS,
    "isinstance": ["isinstance(None, (object,)[0])"],
    "type": ["type((None,)[0]) == object"],
}


def add_io_call(
    modules: list[Module], calls: Mapping[str, list[str]] = IO_CALLS
) -> Iterator[Change]:
    """Each function and method first calls ``print``, ``input`` or ``open``
    (by default): output, keyboard input or file access in code that should
    have none; with ``BUILTIN_CALLS`` also ``isinstance()`` and ``type()``."""
    for module in modules:
        callables = list(class_methods(module.tree)) + list(
            module_functions(module.tree)
        )
        for name, function in sorted(callables, key=lambda item: item[1].lineno):
            if function.body[0].lineno == function.lineno or never_runs(function):
                continue  # a one-line function has no room for it, a stub no run
            at, indent = function_insert(function)
            for member, lines in calls.items():
                yield Change(
                    module.file,
                    f"{module.name}: {name} calls {member}() (line {at + 1})",
                    insert(module.text, at, "\n".join(" " * indent + x for x in lines)),
                    member=member,
                    line=at + 1,
                    function=name,
                )


HELPER_MODULE = "_archtest_helper"


HELPER_SOURCE = "def say(*args):\n    print(*args)\n"


def add_io_via_helper(modules: list[Module]) -> Iterator[Change]:
    """A new module ``_archtest_helper`` prints in ``say``; each function and
    method first imports and calls it, on one line: output that takes a
    detour through a helper outside the function (``member`` is ``print``).
    A module of a package imports it relatively, a top-level module of a
    directory that is no package absolutely."""
    names = {module.name for module in modules}
    if HELPER_MODULE in names:
        return
    helper = f"{HELPER_MODULE}.py"
    for module in modules:
        spelled = relative(module, HELPER_MODULE) if "" in names else HELPER_MODULE
        callables = list(class_methods(module.tree)) + list(
            module_functions(module.tree)
        )
        for name, function in sorted(callables, key=lambda item: item[1].lineno):
            if function.body[0].lineno == function.lineno or never_runs(function):
                continue  # a one-line function has no room for it, a stub no run
            if any(
                isinstance(node, ast.Name) and node.id == "say"
                for node in ast.walk(function)
            ):
                continue  # the import would shadow a name the function uses
            at, indent = function_insert(function)
            line = f'from {spelled} import say; say("archtest")'
            yield Change(
                module.file,
                f"{module.name}: {name} prints through {HELPER_MODULE}.say "
                f"(line {at + 1})",
                insert(module.text, at, " " * indent + line),
                also=((helper, HELPER_SOURCE),),
                member="print",
                line=at + 1,
                function=name,
            )
