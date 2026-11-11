"""Discovery predicates of ``io_separation``.

- ``io``: every function or method whose body calls ``input()``, and every
  entry point: a project function an entry block calls, and a method it
  calls on an object of a project class (``Game().run()``, or ``game =
  Game()`` then ``game.run()``; a method a project base defines counts for
  its subclass). An entry block is an ``if __name__ == "__main__":`` block
  or a bare call at the top of a module (``main()`` at the bottom of the
  file, without the guard); it calls a function by name (defined in the
  same module or imported into it with ``from <module> import <name>``) or
  through a module alias (``game.run()`` after ``import game`` or ``import
  game as g``). Code that calls a pure input helper (below) reads the
  keyboard through it and is ``io`` too: a function when a call resolves
  to the helper through the imports (``ui.ask()`` after ``import ui``,
  ``ask()`` after ``from ui import ask``), wherever it is; a method helper
  is called by its name on an object (``line = self.ask()``) by a method or
  a function of a module with ``io``.
  A function in a module with ``io``, or a method, that an ``io`` function
  or method calls (``show_score(...)``, ``self.view.render(...)``), that
  calls ``print()`` or ``open()``, not ``input()``, returns no value and
  changes nothing (``_mutates``) but calls project code is ``io`` too: user
  interface rather than logic that prints.
- A pure input/output helper is neither ``io`` nor ``logic``. It dispatches
  nothing (a game loop calling ``COMMANDS[verb](...)`` does), is no entry
  point and is held by no table (a dict, list, tuple or set value, as an
  action in ``COMMANDS`` is), and it is one of:

  - an output helper (``_output_helper``), one definition for every scope:
    a function or method that calls ``print()`` or ``open()``, not
    ``input()``, returns no value (no ``return <expr>``), calls nothing of
    the project (``_calls_project``: a project function or class, through
    a module alias, or ``self.m(...)``; ``state.items()`` is no project
    call whatever methods the project has) and changes nothing
    (``_mutates``, alias-aware:
    ``bag = world["bag"]`` then ``bag.append(x)`` changes ``world``). A
    function of a module without ``io`` is one only when the io calls it
    (``show(...)`` imported with ``from display import show``,
    ``display.show(...)``). A game action that prints its result and
    changes the state (``print_instead_of_return``) is therefore logic and
    checked;
  - an input helper: a function in a module whose code reads the keyboard
    or holds an entry point, or a method, that calls ``input()`` and
    nothing of the project (``ask()`` returning ``input("> ")``), when its
    module has an anchor (an entry point, or another function or method
    that is no such candidate and reads the keyboard or calls the helper)
    or has no logic (no function or method but such candidates, entry
    points, keyboard readers and output helpers). An action that reads the
    keyboard among the actions (``actions.take`` calling
    ``input("What? ")`` beside ``actions.look``, called by name from the
    game loop) stays ``io``, so that ``input_in_logic`` is disputed below.
    The candidates are fixed before any is dropped, so the order of the
    entities does not matter.

  Bound to ``io``, a pure helper would have to call the logic
  (``require_runtime_calls``), which it never does; bound to ``logic``, it
  would be reported for the input or output it exists to do.
- ``logic``: what the io code calls directly; what that calls is covered by
  the logic check, which follows calls (``transitive``). A module with a
  top-level public function, no ``io`` entity and no pure helper is bound
  whole, by its module path (so that the check covers the module), when an
  ``io`` function or method calls one of its functions directly:
  ``take(...)`` imported with ``from actions import take``,
  ``actions.take(...)`` after ``import actions``, or a reference to it in a
  table the io code uses (a module-level ``COMMANDS = {"take": take}`` of
  the io's own module or of another project module it imports the table
  from, ``from commands import COMMANDS`` or ``commands.COMMANDS``, a dict
  in the io method's class). In any other module, each top-level public
  function that is neither ``io`` nor a pure helper is bound on its own when
  an ``io`` function or method calls it so. A public method of a project
  class that is neither ``io`` nor a pure helper is logic when an ``io``
  function or method calls it (``obj.m(...)``) or holds it as a value of a
  dispatch dict (a dict value counts only as ``x.m`` with ``m`` a method of
  a project class; other values are data), in its own body or, for an
  ``io`` method, anywhere in its class (``self.commands = {"take":
  self.take}`` in ``__init__``). ``self.m`` is matched against the io
  method's own class family (the class, its project bases and subclasses),
  any other ``x.m`` against every class by the method name. An abstract
  method and every method of an interface class (``ABC``, ``Protocol``,
  ``ABCMeta``, an ``@abstractmethod``) is never matched: no case can build
  its object.

A function that reads the keyboard is ``io`` here even when it is a game
action (``input_in_logic``): only the AI's ``move`` override, accepted when
the project refers to the function elsewhere, makes it logic (the package's
override rules). Such a function is ``io`` with ``disputed`` =
``POSSIBLY_INPUT_IN_LOGIC``, so that the principle cannot be ``ok`` until the
AI moves it or the teacher decides, when it looks like an action:

1. it is no game loop and no dispatcher (it reads the keyboard in no loop and
   calls nothing it looked up in a table such as ``COMMANDS``);
2. it is the only ``io`` entity of its module, and the module has logic;
3. the project refers to it outside its own body and outside an entry
   block (a dispatcher holds it, other code calls it: the test the ``move``
   is accepted by).

An action that reads the keyboard inside a user interface module, a
single-file game, or a method of the same class as the game loop is
therefore not disputed: the AI can still ``move`` it. An action that reads
the keyboard and calls nothing of the project, in a module with an anchor
(a single-file game) or without logic, is a pure helper and is not checked
at all.
"""

from __future__ import annotations

import ast
import dataclasses
from collections.abc import Callable, Mapping, Sequence
from typing import Optional

from pythonarchtesting.entities import Entity
from pythonarchtesting.execution.evaluators.private_access import MUTATING_METHODS
from pythonarchtesting.global_mode.discovery._ast import (
    LITERALS,
    FunctionNode,
    called_names,
    calls_builtin,
    calls_input,
    class_family,
    class_parents,
    classes,
    entry_blocks,
    entry_calls,
    functions,
    imported_names,
    interface_classes,
    is_top_level_public,
    local_bindings,
    module_aliases,
    module_nodes,
    name_of,
    owner_class,
    references_outside,
    runnable_method,
)
from pythonarchtesting.global_mode.model import BoundEntity
from pythonarchtesting.util.module_names import project_module_by_suffix

NOT_FOUND: Mapping[str, str] = {
    "io": (
        "no function calls input() and no project function is called from an "
        'if __name__ == "__main__" block or a bare call at the top of a module'
    ),
    "logic": "the io calls no project function or method directly",
}
# The typical error that hides a role from its predicate: its absence may be
# that error, so the explanation names it.
HIDDEN_BY: Mapping[str, str] = {"logic": "logic_in_main"}
OUTPUT_HELPER = "output helper beside the io"
ENTRY_POINT = "called from the __main__ block"
POSSIBLY_INPUT_IN_LOGIC = (
    "possibly input_in_logic: an action that reads input; move it to logic if "
    "the assignment makes it an action"
)
_OUTPUT = frozenset({"print", "open"})
_IO_BUILTINS = frozenset({"input", "print", "open"})


def _simple(entity: Entity) -> str:
    return entity.qualname.rsplit(".", 1)[-1]


class _Facts:
    """What the code under a node does, worked out once per node within one
    discovery (``calls_input``, ``called_names``): the predicates ask it of
    the same function again for every helper of its module. Keyed by the
    node's identity; the nodes outlive the discovery that holds this."""

    def __init__(self) -> None:
        self._reads: dict[int, bool] = {}
        self._called: dict[int, set[str]] = {}

    def reads(self, node: ast.AST) -> bool:
        """``calls_input(node)``."""
        key = id(node)
        if key not in self._reads:
            self._reads[key] = calls_input(node)
        return self._reads[key]

    def called(self, node: ast.AST) -> set[str]:
        """``called_names(node)``; the set is shared, never change it."""
        key = id(node)
        if key not in self._called:
            self._called[key] = called_names(node)
        return self._called[key]


def _entry_functions(
    trees: Sequence[tuple[str, ast.Module]], top_level: set[str]
) -> set[str]:
    """The project functions an entry block (``entry_blocks``) calls: by
    name, defined in the same module or imported with ``from <module> import
    <name>``, or through a module alias (``game.run()`` after ``import
    game`` or ``import game as g``)."""
    modules = [module for module, _ in trees]
    found: set[str] = set()
    for module, tree in trees:
        context = {module: (imported_names(tree), module_aliases(tree, modules))}
        for call in entry_calls(tree):
            found |= _calls_resolved(call, module, context, modules, top_level)
    return found


def _class_lookup(
    module: str, tree: ast.Module, class_names: set[str], modules: Sequence[str]
) -> Callable[[str], Optional[str]]:
    """The project class a plain name in ``module`` stands for, else ``None``."""
    imported = imported_names(tree)

    def lookup(local: str) -> Optional[str]:
        if f"{module}.{local}" in class_names:
            return f"{module}.{local}"
        if local in imported:
            written, original = imported[local]
            source = project_module_by_suffix(written, modules)
            if source is not None and f"{source}.{original}" in class_names:
                return f"{source}.{original}"
        return None

    return lookup


def _method_of(
    cls: str, method: str, methods: set[str], parents: Mapping[str, list[str]]
) -> Optional[str]:
    """The method ``method`` an object of ``cls`` runs: the class's own, else
    the nearest project base's."""
    todo, seen = [cls], set()
    while todo:
        current = todo.pop(0)
        if current in seen:
            continue
        seen.add(current)
        if f"{current}.{method}" in methods:
            return f"{current}.{method}"
        todo.extend(parents.get(current, []))
    return None


def _entry_methods(
    entities: Sequence[Entity], trees: Sequence[tuple[str, ast.Module]]
) -> set[str]:
    """The methods an entry block (``entry_blocks``) calls on an object of a
    project class: ``Game().run()``, or ``game = Game()`` and then
    ``game.run()``."""
    modules = [module for module, _ in trees]
    class_names = {name_of(e) for e, _ in classes(entities)}
    methods = {name_of(e) for e, _ in functions(entities) if e.kind == "method"}
    parents = class_parents(entities)
    found: set[str] = set()
    for module, tree in trees:
        lookup = _class_lookup(module, tree, class_names, modules)
        blocks = entry_blocks(tree)
        # ``game = Game()`` may stand at the top of the module, before a bare
        # ``game.run()``.
        assigned = [s for s in tree.body if isinstance(s, ast.Assign)]
        instances: dict[str, str] = {}
        for statement in [*blocks, *assigned]:
            for node in ast.walk(statement):
                if (
                    isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and (cls := lookup(node.value.func.id)) is not None
                ):
                    instances[node.targets[0].id] = cls
        for node in entry_calls(tree):
            if not isinstance(node.func, ast.Attribute):
                continue
            receiver = node.func.value
            owner: Optional[str] = None
            if isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Name):
                owner = lookup(receiver.func.id)
            elif isinstance(receiver, ast.Name):
                owner = instances.get(receiver.id)
            if owner is not None:
                method = _method_of(owner, node.func.attr, methods, parents)
                if method is not None:
                    found.add(method)
    return found


def _held_in_tables(trees: Sequence[tuple[str, ast.Module]]) -> set[str]:
    """The last name segments of what a dict, list, tuple or set of the
    project holds as a value: ``take`` of ``{"take": take}``, ``go`` of
    ``{"go": self.go}``."""
    found: set[str] = set()
    for _, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                values: list[ast.expr] = [v for v in node.values if v is not None]
            elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                values = list(node.elts)
            else:
                continue
            for value in values:
                if isinstance(value, ast.Name):
                    found.add(value.id)
                elif isinstance(value, ast.Attribute):
                    found.add(value.attr)
    return found


def _pure_helpers(
    every: Sequence[tuple[Entity, FunctionNode]],
    entry: set[str],
    reading_modules: set[str],
    trees: Sequence[tuple[str, ast.Module]],
    callers: set[str],
    facts: _Facts,
) -> dict[str, FunctionNode]:
    """The pure input/output helpers (module docstring), by name: the
    output helpers (``_output_helper``) and the input helper candidates
    (they read the keyboard and call nothing of the project) whose module
    has an anchor or no logic. ``callers`` are the functions and methods
    that call project code (``_calls_project``)."""
    calls_input = facts.reads
    called_names = facts.called
    tables = _held_in_tables(trees)
    pure = {
        name_of(entity): node
        for entity, node in every
        if name_of(entity) not in entry
        and (entity.module_path in reading_modules or entity.kind == "method")
        and _simple(entity) not in tables
        and not _dispatches(node)
        and (
            (calls_input(node) and name_of(entity) not in callers)
            or _output_helper(node, name_of(entity) in callers)
        )
    }
    # The input helper candidates, fixed before any is dropped, so that the
    # outcome does not depend on the order of the entities.
    candidates = {name for name, node in pure.items() if calls_input(node)}
    by_module: dict[str, list[tuple[Entity, FunctionNode]]] = {}
    for entity, node in every:
        by_module.setdefault(entity.module_path, []).append((entity, node))

    def anchored(helper: str, module: str) -> bool:
        """Whether the helper's module has an entry point or another io
        entity that is no helper candidate (it reads the keyboard or calls
        the helper)."""
        simple = helper.rsplit(".", 1)[-1]
        return any(
            name_of(entity) not in candidates
            and name_of(entity) != helper
            and (
                name_of(entity) in entry
                or calls_input(node)
                or simple in called_names(node)
            )
            for entity, node in by_module[module]
        )

    def has_logic(module: str) -> bool:
        """Whether the module has a function or method that is no helper
        candidate, no entry point, reads no keyboard and is no output helper
        (``_output_helper``)."""
        return any(
            name_of(entity) not in candidates
            and name_of(entity) not in entry
            and not calls_input(node)
            and not _output_helper(node, name_of(entity) in callers)
            for entity, node in by_module[module]
        )

    for entity, node in every:
        name = name_of(entity)
        module = entity.module_path
        if name in candidates and not anchored(name, module) and has_logic(module):
            del pure[name]
    return pure


_ModuleContexts = dict[str, tuple[dict[str, tuple[str, str]], dict[str, str]]]


@dataclasses.dataclass(frozen=True)
class _IoContext:
    """What ``_io`` works out of the submission once before it binds anything:
    the functions and methods (``every``), the modules, their imports
    (``contexts``), the top-level functions, the entry points, the modules
    that read the keyboard or hold an entry point (``reading_modules``) and
    the functions and methods that call project code (``callers``). It also
    keeps the project functions each ``def`` calls (``resolved``), so that
    the growth of the output helpers does not resolve the calls of an ``io``
    entity again on every round."""

    facts: _Facts
    every: list[tuple[Entity, FunctionNode]]
    trees: list[tuple[str, ast.Module]]
    modules: list[str]
    contexts: _ModuleContexts
    top_level: set[str]
    entry: set[str]
    reading_modules: set[str]
    callers: set[str]
    _resolved: dict[int, set[str]] = dataclasses.field(default_factory=dict)

    def resolved(self, entity: Entity, node: FunctionNode) -> set[str]:
        """``_calls_resolved`` of ``node``, the ``def`` of ``entity``, worked
        out once per node; the set is shared, never change it."""
        key = id(node)
        if key not in self._resolved:
            self._resolved[key] = _calls_resolved(
                node, entity.module_path, self.contexts, self.modules, self.top_level
            )
        return self._resolved[key]


def _io_context(entities: Sequence[Entity]) -> _IoContext:
    """The facts of ``entities`` that ``_io`` asks for (``_IoContext``)."""
    facts = _Facts()
    every = functions(entities)
    trees = module_nodes(entities)
    modules = [module for module, _ in trees]
    top_level = {
        name_of(e) for e, _ in every if e.kind == "function" and "." not in e.qualname
    }
    entry = _entry_functions(trees, top_level) | _entry_methods(entities, trees)
    reading_modules = {
        e.module_path for e, node in every if facts.reads(node) or name_of(e) in entry
    }
    contexts = {
        module: (imported_names(tree), module_aliases(tree, modules))
        for module, tree in trees
    }
    known = top_level | {name_of(e) for e, _ in classes(entities)}
    callers = {
        name_of(e)
        for e, node in every
        if _calls_project(node, e.module_path, contexts, modules, known)
    }
    return _IoContext(
        facts=facts,
        every=every,
        trees=trees,
        modules=modules,
        contexts=contexts,
        top_level=top_level,
        entry=entry,
        reading_modules=reading_modules,
        callers=callers,
    )


def _io(entities: Sequence[Entity]) -> tuple[list[BoundEntity], set[str]]:
    """The ``io`` candidates and the pure helpers (module docstring)."""
    ctx = _io_context(entities)
    pure = _pure_helpers(
        ctx.every, ctx.entry, ctx.reading_modules, ctx.trees, ctx.callers, ctx.facts
    )
    io = _reading_io(pure, ctx)
    _grow_output_helpers(io, pure, ctx)
    return [io[name] for name in sorted(io)], set(pure)


def _reading_io(
    pure: Mapping[str, FunctionNode], ctx: _IoContext
) -> dict[str, BoundEntity]:
    """The ``io`` entities that are no pure helper and read the keyboard, are
    an entry point, or read it through a pure input helper, by name, each
    with its reasons (``_io_reasons``)."""
    # A pure input helper is called by what it is: a function through the
    # imports (``ask()``, ``ui.ask()``), a method by its name on an object.
    readers = {name for name, node in pure.items() if ctx.facts.reads(node)}
    reader_methods = {n.rsplit(".", 1)[-1] for n in readers if n not in ctx.top_level}
    io: dict[str, BoundEntity] = {}
    for entity, node in ctx.every:
        name = name_of(entity)
        if name in pure:
            continue
        reasons = _io_reasons(entity, node, ctx, readers, reader_methods)
        if reasons:
            io[name] = BoundEntity(name, "code", "; ".join(reasons))
    return io


def _io_reasons(
    entity: Entity,
    node: FunctionNode,
    ctx: _IoContext,
    readers: set[str],
    reader_methods: set[str],
) -> list[str]:
    """Why ``entity`` is ``io``, in a fixed order: it calls ``input()``, it is
    an entry point, it reads the keyboard through the pure input helpers
    ``readers`` (a call resolved through the imports, or a method helper
    called by its name, ``reader_methods``, from a method or a function of a
    module that reads the keyboard). Empty when it is not ``io`` so."""
    reasons = []
    if ctx.facts.reads(node):
        reasons.append("calls input()")
    if name_of(entity) in ctx.entry:
        reasons.append(ENTRY_POINT)
    through = {f.rsplit(".", 1)[-1] for f in ctx.resolved(entity, node) & readers}
    if entity.module_path in ctx.reading_modules or entity.kind == "method":
        through |= ctx.facts.called(node) & reader_methods
    if through:
        reasons.append(
            "reads input through " + ", ".join(f"{t}()" for t in sorted(through))
        )
    return reasons


def _output_candidates(
    io: Mapping[str, BoundEntity], pure: Mapping[str, FunctionNode], ctx: _IoContext
) -> list[tuple[Entity, FunctionNode]]:
    """The functions and methods, neither ``io`` nor pure yet, that call
    ``print()`` or ``open()``, not ``input()``, return no value and change
    nothing: what ``_grow_output_helpers`` may bind when the ``io`` calls
    it. Filtered once, before the growth."""
    return [
        (entity, node)
        for entity, node in ctx.every
        if name_of(entity) not in io
        and name_of(entity) not in pure
        and calls_builtin(node, _OUTPUT)
        and not ctx.facts.reads(node)
        and not _returns_value(node)
        and not _mutates(node)
    ]


def _called_by_io(
    entity: Entity, ctx: _IoContext, called: set[str], resolved: set[str]
) -> bool:
    """Whether the ``io`` calls ``entity``: a top-level function when a call
    resolves to it (``resolved``), a method (or a nested function) when one
    has its name (``called``)."""
    name = name_of(entity)
    if name in ctx.top_level:
        return name in resolved
    return _simple(entity) in called


def _grow_output_helpers(
    io: dict[str, BoundEntity], pure: dict[str, FunctionNode], ctx: _IoContext
) -> None:
    """Bind, in place, the output helpers the ``io`` calls until nothing new
    is bound: one that calls nothing of the project (``_output_helper``) is
    a pure helper (it goes to ``pure``), one that calls project code is
    ``io`` (``OUTPUT_HELPER``) when it is a method or in a module that had
    ``io`` before the growth. A new ``io`` entity may call further helpers,
    hence the rounds."""
    io_modules = {e.module_path for e, _ in ctx.every if name_of(e) in io}
    helpers = _output_candidates(io, pure, ctx)
    # The last ``def`` of each name, as the calls of an io entity are read.
    defs = {name_of(e): (e, node) for e, node in ctx.every}
    grown = True
    while grown:
        grown = False
        called = set().union(*(ctx.facts.called(defs[name][1]) for name in io))
        resolved = set().union(*(ctx.resolved(*defs[name]) for name in io))
        for entity, node in helpers:
            name = name_of(entity)
            if name in io or name in pure:
                continue
            if not _called_by_io(entity, ctx, called, resolved):
                continue
            if _output_helper(node, name in ctx.callers):
                # Prints what it is given and changes nothing: UI.
                pure[name] = node
            elif entity.module_path in io_modules or entity.kind == "method":
                # Prints, changes nothing and calls project code: io.
                io[name] = BoundEntity(name, "code", OUTPUT_HELPER)
                grown = True


_FRESH_BUILTINS = frozenset(
    {
        "list",
        "dict",
        "set",
        "tuple",
        "str",
        "int",
        "float",
        "bool",
        "sorted",
        "frozenset",
        "len",
        "range",
        "repr",
        "format",
        "abs",
    }
)


def _fresh_locals(node: FunctionNode) -> set[str]:
    """The function's local names that only ever hold an object it built
    itself: every binding is a literal, a comprehension, a call of a builtin
    constructor (``list(...)``, ``sorted(...)``), a string, or arithmetic on
    such values. A name bound from a parameter, an attribute, an item or a
    global, directly or through another such name, is not one. ``x += v``
    is no binding here: it changes ``x`` (``_mutates``), it does not say
    what ``x`` holds."""
    params = {a.arg for a in ast.walk(node.args) if isinstance(a, ast.arg)}
    bindings = {k: v for k, v in local_bindings(node).items() if k not in params}
    fresh = set(bindings)

    def builds(value: Optional[ast.expr]) -> bool:
        if value is None:
            return False
        if isinstance(value, ast.Name):
            return value.id in fresh
        if isinstance(value, LITERALS):
            return True
        if isinstance(value, ast.Call):
            return isinstance(value.func, ast.Name) and value.func.id in _FRESH_BUILTINS
        if isinstance(value, ast.BinOp):
            return builds(value.left) and builds(value.right)
        if isinstance(value, ast.UnaryOp):
            return builds(value.operand)
        return False

    changed = True
    while changed:
        changed = False
        for name in sorted(fresh):
            if not all(builds(v) for v in bindings[name]):
                fresh.discard(name)
                changed = True
    return fresh


def _root_name(target: ast.expr) -> Optional[str]:
    """The name an attribute or item chain starts at (``a`` of ``a.b[0]``)."""
    while isinstance(target, (ast.Attribute, ast.Subscript)):
        target = target.value
    return target.id if isinstance(target, ast.Name) else None


def _mutates(node: FunctionNode) -> bool:
    """Whether the function changes anything but objects it built itself
    (``_fresh_locals``): it declares a name ``global`` or ``nonlocal``,
    stores to or deletes an attribute or an item of anything else, assigns
    with ``+=`` and the like to a name that is no such local (a parameter, a
    global, or an alias of one: ``held = pack`` then ``held += [x]``), or
    calls a mutating method of the core (``MUTATING_METHODS``: ``append``,
    ``pop``, ``clear``, ``sort``, ...) on anything else. ``bag =
    world["bag"]`` then ``bag.append(x)`` changes ``world``; ``total = 0``
    then ``total += price`` changes nothing."""
    fresh = _fresh_locals(node)
    for n in ast.walk(node):
        if isinstance(n, (ast.Global, ast.Nonlocal)):
            return True
        if isinstance(n, (ast.Attribute, ast.Subscript)) and isinstance(
            n.ctx, (ast.Store, ast.Del)
        ):
            if _root_name(n) not in fresh:
                return True
        if (
            isinstance(n, ast.AugAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id not in fresh
        ):
            return True
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr in MUTATING_METHODS
            and not (isinstance(n.func.value, ast.Name) and n.func.value.id in fresh)
        ):
            return True
    return False


def _output_helper(node: FunctionNode, calls_project: bool) -> bool:
    """Whether the function is an output helper of the user interface: it
    calls ``print()`` or ``open()``, not ``input()``, returns no value, calls
    nothing of the project (``calls_project`` false, see ``_calls_project``)
    and changes nothing (``_mutates``)."""
    return (
        calls_builtin(node, _OUTPUT)
        and not calls_input(node)
        and not _returns_value(node)
        and not calls_project
        and not _mutates(node)
    )


def _calls_project(
    node: FunctionNode,
    module: str,
    contexts: Mapping[str, tuple[dict[str, tuple[str, str]], dict[str, str]]],
    modules: Sequence[str],
    known: set[str],
) -> bool:
    """Whether the code of ``node`` (in ``module``) calls project code it can
    be told to call: a top-level function or class of the project by its
    name (``known``: defined in ``module``, or anything imported with ``from
    <project module> import``), anything through a module alias
    (``actions.take(...)``), a method of the object itself (``self.m(...)``,
    ``cls.m(...)``) or of a project class named (``Shop.price(...)``). A
    method call on any other object (``state.items()``, ``text.format()``)
    is a builtin one as far as the code can tell: a project method of the
    same name does not make it a project call."""
    imported, aliases = contexts.get(module, ({}, {}))

    def project_name(local: str) -> bool:
        if f"{module}.{local}" in known:
            return True
        return (
            local in imported
            and project_module_by_suffix(imported[local][0], modules) is not None
        )

    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        if isinstance(n.func, ast.Name) and project_name(n.func.id):
            return True
        if isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name):
            receiver = n.func.value.id
            if (
                receiver in aliases
                or receiver in ("self", "cls")
                or project_name(receiver)
            ):
                return True
    return False


def _returns_value(node: FunctionNode) -> bool:
    """Whether the function has a ``return <expr>`` of its own (``return``
    alone and ``return None`` return no value); a nested function's return
    does not count."""
    stack: list[ast.AST] = list(node.body)
    while stack:
        current = stack.pop()
        if isinstance(
            current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
        ):
            continue
        if isinstance(current, ast.Return) and current.value is not None:
            if not (
                isinstance(current.value, ast.Constant) and current.value.value is None
            ):
                return True
        stack.extend(ast.iter_child_nodes(current))
    return False


def _calls_resolved(
    node: ast.AST,
    module: str,
    contexts: Mapping[str, tuple[dict[str, tuple[str, str]], dict[str, str]]],
    modules: Sequence[str],
    top_level: set[str],
) -> set[str]:
    """The project top-level functions the code of ``node`` (in ``module``)
    calls: ``f(...)`` defined in ``module`` or imported with ``from <m>
    import f``, and ``m.f(...)`` after ``import m``."""
    imported, aliases = contexts.get(module, ({}, {}))
    found: set[str] = set()
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        qualified: Optional[str] = None
        if isinstance(n.func, ast.Name):
            if f"{module}.{n.func.id}" in top_level:
                qualified = f"{module}.{n.func.id}"
            elif n.func.id in imported:
                written, original = imported[n.func.id]
                source = project_module_by_suffix(written, modules)
                if source is not None:
                    qualified = f"{source}.{original}"
        elif (
            isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id in aliases
        ):
            qualified = f"{aliases[n.func.value.id]}.{n.func.attr}"
        if qualified is not None and qualified in top_level:
            found.add(qualified)
    return found


def _module_tables(tree: ast.Module) -> dict[str, ast.expr]:
    """``name -> value`` of the module's top-level assignments (a table such
    as ``COMMANDS = {"take": take}``)."""
    return {
        target.id: statement.value
        for statement in tree.body
        if isinstance(statement, ast.Assign)
        for target in statement.targets
        if isinstance(target, ast.Name)
    }


def _names_in(value: ast.expr) -> list[ast.expr]:
    return [m for m in ast.walk(value) if isinstance(m, (ast.Name, ast.Attribute))]


def _references(
    node: FunctionNode,
    module: str,
    trees: Mapping[str, ast.Module],
    class_node: Optional[ast.ClassDef],
) -> list[tuple[ast.expr, str]]:
    """What io code in ``module`` refers to, each with the module it is
    written in: the names and attributes read in its own body, in the dict
    values of its class (for a method) and in the value of a module-level
    table its body reads, of its own module (``COMMANDS = {"take": take}``)
    or imported from another project module (``from commands import
    COMMANDS``, ``commands.COMMANDS``)."""
    modules = sorted(trees)
    tree = trees[module]
    tables = _module_tables(tree)
    imported = imported_names(tree)
    aliases = module_aliases(tree, modules)

    def table_of(ref: ast.expr) -> Optional[tuple[ast.expr, str]]:
        """The value of the table ``ref`` names and the module it is in."""
        if isinstance(ref, ast.Name):
            if ref.id in tables:
                return tables[ref.id], module
            if ref.id in imported:
                written, original = imported[ref.id]
                source = project_module_by_suffix(written, modules)
                if source is not None and source != module:
                    value = _module_tables(trees[source]).get(original)
                    if value is not None:
                        return value, source
        elif (
            isinstance(ref, ast.Attribute)
            and isinstance(ref.value, ast.Name)
            and ref.value.id in aliases
            and aliases[ref.value.id] != module
        ):
            source = aliases[ref.value.id]
            value = _module_tables(trees[source]).get(ref.attr)
            if value is not None:
                return value, source
        return None

    roots: list[ast.AST] = [node]
    if class_node is not None:
        roots.extend(
            value
            for n in ast.walk(class_node)
            if isinstance(n, ast.Dict)
            for value in n.values
        )
    found: list[tuple[ast.expr, str]] = []
    for root in roots:
        for n in ast.walk(root):
            if isinstance(n, (ast.Name, ast.Attribute)) and isinstance(n.ctx, ast.Load):
                found.append((n, module))
                table = table_of(n) if root is node else None
                if table is not None:
                    found.extend((m, table[1]) for m in _names_in(table[0]))
    return found


def _called_directly(
    entities: Sequence[Entity], io_names: set[str]
) -> tuple[set[str], set[str]]:
    """The project modules and top-level functions the io code calls or
    refers to directly (module docstring)."""
    every = functions(entities)
    trees = dict(module_nodes(entities))
    modules = sorted(trees)
    class_nodes = {(e.module_path, e.qualname): node for e, node in classes(entities)}
    top_level = {
        name_of(e) for e, _ in every if e.kind == "function" and "." not in e.qualname
    }
    imports = {module: imported_names(tree) for module, tree in trees.items()}
    aliases = {module: module_aliases(tree, modules) for module, tree in trees.items()}
    called_modules: set[str] = set()
    called: set[str] = set()
    for entity, node in every:
        if name_of(entity) not in io_names or entity.module_path not in trees:
            continue
        owner = owner_class(entity)
        refs = _references(
            node, entity.module_path, trees, class_nodes.get(owner) if owner else None
        )
        for ref, module in refs:
            qualified: Optional[str] = None
            if isinstance(ref, ast.Name):
                if f"{module}.{ref.id}" in top_level:
                    qualified = f"{module}.{ref.id}"
                elif ref.id in imports[module]:
                    written, original = imports[module][ref.id]
                    source = project_module_by_suffix(written, modules)
                    if source is not None:
                        qualified = f"{source}.{original}"
            elif isinstance(ref, ast.Attribute) and isinstance(ref.value, ast.Name):
                if ref.value.id in aliases[module]:
                    qualified = f"{aliases[module][ref.value.id]}.{ref.attr}"
            if qualified is not None and qualified in top_level:
                called.add(qualified)
                called_modules.add(qualified.rsplit(".", 1)[0])
    return called_modules, called


def _logic_functions(
    entities: Sequence[Entity], io_names: set[str], pure: set[str]
) -> dict[str, BoundEntity]:
    """The modules and top-level functions of ``logic`` (module docstring)."""
    every = functions(entities)
    called_modules, called = _called_directly(entities, io_names)
    io_modules = {e.module_path for e, _ in every if name_of(e) in io_names}
    pure_modules = {e.module_path for e, _ in every if name_of(e) in pure}
    logic: dict[str, BoundEntity] = {}
    for module in sorted({e.module_path for e, _ in every}):
        public = [
            e for e, _ in every if e.module_path == module and is_top_level_public(e)
        ]
        if not public:
            continue
        if module not in io_modules and module not in pure_modules:
            if module in called_modules:
                logic[module] = BoundEntity(
                    module,
                    "code",
                    "module of top-level functions without io, called by the io",
                )
            continue
        for e in public:
            name = name_of(e)
            if name not in io_names and name not in pure and name in called:
                logic[name] = BoundEntity(
                    name, "code", f"top-level function of {module} the io calls"
                )
    return logic


def _method_ref(attr: ast.Attribute) -> tuple[str, bool]:
    """``(m, on self)`` of ``x.m``: ``on self`` when ``x`` is ``self``."""
    return attr.attr, isinstance(attr.value, ast.Name) and attr.value.id == "self"


def _dispatched(node: ast.Dict, methods: set[str]) -> list[ast.Attribute]:
    """The values ``x.m`` of a dict, ``m`` among ``methods``."""
    return [
        v for v in node.values if isinstance(v, ast.Attribute) and v.attr in methods
    ]


def _method_refs(node: ast.AST, methods: set[str]) -> set[tuple[str, bool]]:
    """``_method_ref`` of each ``x.m(...)`` call under ``node`` and of each
    dict value ``x.m``, ``m`` among ``methods`` (``_dispatched``)."""
    found: set[tuple[str, bool]] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            found.add(_method_ref(n.func))
        elif isinstance(n, ast.Dict):
            found.update(_method_ref(v) for v in _dispatched(n, methods))
    return found


def _dispatched_in_class(
    node: ast.ClassDef, methods: set[str]
) -> set[tuple[str, bool]]:
    """``_method_ref`` of each dict value ``x.m`` in the class (``_dispatched``)."""
    return {
        _method_ref(v)
        for n in ast.walk(node)
        if isinstance(n, ast.Dict)
        for v in _dispatched(n, methods)
    }


def _used_methods(
    entities: Sequence[Entity], io_names: set[str], pure: set[str]
) -> dict[str, BoundEntity]:
    """The public non-io methods the io code calls or dispatches (module
    docstring)."""
    class_nodes = {(e.module_path, e.qualname): node for e, node in classes(entities)}
    every = functions(entities)
    interfaces = interface_classes(entities)
    family = class_family(entities)
    methods = {_simple(e) for e, _ in every if e.kind == "method"}
    eligible: dict[str, list[Entity]] = {}
    for entity, node in every:
        name = name_of(entity)
        if (
            entity.kind == "method"
            and not _simple(entity).startswith("_")
            and name not in io_names
            and name not in pure
            and runnable_method(entity, node, interfaces)
        ):
            eligible.setdefault(_simple(entity), []).append(entity)

    def matching(method: str, on_self: bool, owner: Optional[str]) -> list[str]:
        found = eligible.get(method, [])
        if on_self and owner is not None:
            relatives = family(owner)
            found = [
                e
                for e in found
                if (o := owner_class(e)) and f"{o[0]}.{o[1]}" in relatives
            ]
        return [name_of(e) for e in found]

    used: dict[str, BoundEntity] = {}
    for entity, node in every:
        if name_of(entity) not in io_names:
            continue
        owner = owner_class(entity)
        cls = f"{owner[0]}.{owner[1]}" if owner else None
        why = f"method the io {name_of(entity)} calls or dispatches"
        for method, on_self in sorted(_method_refs(node, methods)):
            for name in matching(method, on_self, cls):
                used.setdefault(name, BoundEntity(name, "code", why))
    for entity, _ in every:
        owner = owner_class(entity)
        if name_of(entity) not in io_names or owner is None or owner not in class_nodes:
            continue
        cls = f"{owner[0]}.{owner[1]}"
        why = f"method in a dispatch dict of {cls}, a class with io"
        for method, on_self in sorted(
            _dispatched_in_class(class_nodes[owner], methods)
        ):
            for name in matching(method, on_self, cls):
                used.setdefault(name, BoundEntity(name, "code", why))
    return used


def find(entities: Sequence[Entity]) -> dict[str, list[BoundEntity]]:
    """The candidates of ``io`` and ``logic`` in ``entities``."""
    every = functions(entities)
    io, pure = _io(entities)
    io_names = {b.entity for b in io}
    logic = _logic_functions(entities, io_names, pure)
    for name, bound in _used_methods(entities, io_names, pure).items():
        logic.setdefault(name, bound)
    return {
        "io": _disputed_actions(io, every, logic, entities),
        "logic": [logic[name] for name in sorted(logic)],
    }


def _is_input(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "input"
    )


def _lookup(node: ast.AST) -> bool:
    """Whether ``node`` looks a value up in a table: ``t[k]`` or ``t.get(k)``."""
    return isinstance(node, ast.Subscript) or (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
    )


def _loop_or_dispatcher(node: FunctionNode) -> bool:
    """Whether the function reads the keyboard in a loop, or calls what it
    looked up in a table (``COMMANDS[verb](...)``, ``action = t.get(verb)``
    then ``action(...)``): a game loop or a dispatcher, UI by construction."""
    loops = (ast.While, ast.For, ast.AsyncFor)
    if any(
        isinstance(loop, loops) and any(_is_input(n) for n in ast.walk(loop))
        for loop in ast.walk(node)
    ):
        return True
    return _dispatches(node)


def _dispatches(node: ast.AST) -> bool:
    """Whether the code under ``node`` calls what it looked up in a table
    (``COMMANDS[verb](...)``, ``action = t.get(verb)`` then ``action(...)``)
    or by name (``getattr(self, verb)(...)``)."""
    looked_up = {
        target.id
        for n in ast.walk(node)
        if isinstance(n, ast.Assign) and _lookup(n.value)
        for target in n.targets
        if isinstance(target, ast.Name)
    }
    return any(
        isinstance(n, ast.Call)
        and (
            _lookup(n.func)
            or (isinstance(n.func, ast.Name) and n.func.id in looked_up)
            or (isinstance(n.func, ast.Name) and n.func.id == "getattr")
        )
        for n in ast.walk(node)
    )


def _disputed_actions(
    io: list[BoundEntity],
    every: Sequence[tuple[Entity, FunctionNode]],
    logic: Mapping[str, BoundEntity],
    entities: Sequence[Entity],
) -> list[BoundEntity]:
    """``io`` with each candidate that may be a game action reading the
    keyboard disputed (module docstring). Every one of these holds:

    1. it calls ``input()`` and is no game loop or dispatcher
       (``_loop_or_dispatcher``);
    2. it is the only ``io`` entity of its module, and the module has logic:
       it sits among the actions, not in a user interface;
    3. the project refers to it outside its own body and an entry block
       (``references_outside``, the test of the ``move``).
    """
    logic_modules = {e.module_path for e, _ in every if name_of(e) in logic} | {
        name for name in logic if any(e.module_path == name for e, _ in every)
    }
    nodes = {name_of(e): (e, node) for e, node in every}
    io_per_module: dict[str, int] = {}
    for bound in io:
        module = nodes[bound.entity][0].module_path
        io_per_module[module] = io_per_module.get(module, 0) + 1
    found = []
    for bound in io:
        entity, node = nodes[bound.entity]
        if (
            calls_input(node)
            and not _loop_or_dispatcher(node)
            and io_per_module[entity.module_path] == 1
            and entity.module_path in logic_modules
            and references_outside(entity, entities)
        ):
            bound = dataclasses.replace(bound, disputed=POSSIBLY_INPUT_IN_LOGIC)
        found.append(bound)
    return found


__all__ = [
    "ENTRY_POINT",
    "HIDDEN_BY",
    "NOT_FOUND",
    "OUTPUT_HELPER",
    "POSSIBLY_INPUT_IN_LOGIC",
    "find",
]
