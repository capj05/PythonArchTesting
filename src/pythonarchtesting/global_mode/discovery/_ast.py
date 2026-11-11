"""AST helpers shared by the discovery predicates. They read the nodes the
core's extraction keeps in ``Entity.extras["ast_node"]`` and run no code."""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import PurePosixPath
from typing import Optional, Union

from pythonarchtesting.entities import Entity
from pythonarchtesting.principles.task import entity_name
from pythonarchtesting.util.ast_utils import is_abstract_or_stub, is_interface
from pythonarchtesting.util.module_names import project_module_by_suffix

FunctionNode = Union[ast.FunctionDef, ast.AsyncFunctionDef]
# The expressions that build a new builtin object: a literal, an f-string, a
# comprehension.
LITERALS = (
    ast.Constant,
    ast.JoinedStr,
    ast.List,
    ast.Tuple,
    ast.Set,
    ast.Dict,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


def name_of(entity: Entity) -> str:
    """The entity's name as the self-task binds it (``task.entity_name``):
    ``actions`` for a module, ``ship.Cargo.load`` for a method."""
    return entity_name(entity)


def function_node(entity: Entity) -> Optional[FunctionNode]:
    """The ``def`` of a function or method entity, else ``None``."""
    node = entity.extras.get("ast_node")
    if entity.kind in ("function", "method") and isinstance(
        node, (ast.FunctionDef, ast.AsyncFunctionDef)
    ):
        return node
    return None


def class_node(entity: Entity) -> Optional[ast.ClassDef]:
    """The ``class`` statement of a class entity, else ``None``."""
    node = entity.extras.get("ast_node")
    return node if entity.kind == "class" and isinstance(node, ast.ClassDef) else None


def module_nodes(entities: Sequence[Entity]) -> list[tuple[str, ast.Module]]:
    """``(module path, tree)`` of every module of the submission, by path."""
    found = {
        e.module_path: node
        for e in entities
        if e.kind == "module"
        and isinstance(node := e.extras.get("ast_node"), ast.Module)
    }
    return sorted(found.items())


def functions(entities: Sequence[Entity]) -> list[tuple[Entity, FunctionNode]]:
    """Every function and method with its ``def``, by name."""
    found = [(e, node) for e in entities if (node := function_node(e)) is not None]
    return sorted(found, key=lambda pair: name_of(pair[0]))


def classes(entities: Sequence[Entity]) -> list[tuple[Entity, ast.ClassDef]]:
    """Every class with its ``class`` statement, by name."""
    found = [(e, node) for e in entities if (node := class_node(e)) is not None]
    return sorted(found, key=lambda pair: name_of(pair[0]))


def is_top_level_public(entity: Entity) -> bool:
    """A public function at the top of its module: what ``task.resolve_name``
    binds when a role names the whole module."""
    return (
        entity.kind == "function"
        and "." not in entity.qualname
        and not entity.qualname.startswith("_")
    )


def owner_class(entity: Entity) -> Optional[tuple[str, str]]:
    """``(module path, class qualname)`` of a method, else ``None``."""
    if entity.kind != "method" or "." not in entity.qualname:
        return None
    return entity.module_path, entity.qualname.rsplit(".", 1)[0]


def calls_input(node: ast.AST) -> bool:
    """Whether the code under ``node`` calls ``input(...)``."""
    return any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "input"
        for n in ast.walk(node)
    )


def calls_builtin(node: ast.AST, names: frozenset[str]) -> bool:
    """Whether the code under ``node`` calls one of ``names`` by plain name."""
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in names
        for n in ast.walk(node)
    )


def called_names(node: ast.AST) -> set[str]:
    """The names the code under ``node`` calls, as ``f(...)`` or ``x.f(...)``."""
    found: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name):
                found.add(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                found.add(n.func.attr)
    return found


def local_bindings(node: FunctionNode) -> dict[str, list[Optional[ast.expr]]]:
    """What each name of the function's own body is bound to: the value of
    ``x = v``, ``x: T = v`` or ``x := v``, and ``None`` for a binding whose
    value is unknown (a loop or ``with`` target, an unpacking, an import, a
    ``def``). Nested functions and classes are not looked into."""
    found: dict[str, list[Optional[ast.expr]]] = {}

    def bind(target: ast.AST, value: Optional[ast.expr]) -> None:
        if isinstance(target, ast.Name):
            found.setdefault(target.id, []).append(value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                bind(element, None)
        elif isinstance(target, ast.Starred):
            bind(target.value, None)

    stack: list[ast.AST] = list(node.body)
    while stack:
        current = stack.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.setdefault(current.name, []).append(None)
            continue
        if isinstance(current, ast.Lambda):
            continue
        if isinstance(current, ast.Assign):
            for target in current.targets:
                bind(target, current.value)
        elif isinstance(current, ast.AnnAssign):
            if current.value is not None:
                bind(current.target, current.value)
        elif isinstance(current, ast.NamedExpr):
            bind(current.target, current.value)
        elif isinstance(current, (ast.For, ast.AsyncFor)):
            bind(current.target, None)
        elif isinstance(current, (ast.With, ast.AsyncWith)):
            for item in current.items:
                if item.optional_vars is not None:
                    bind(item.optional_vars, None)
        elif isinstance(current, (ast.Import, ast.ImportFrom)):
            for alias in current.names:
                found.setdefault((alias.asname or alias.name).split(".")[0], []).append(
                    None
                )
        elif isinstance(current, ast.ExceptHandler) and current.name:
            found.setdefault(current.name, []).append(None)
        if isinstance(
            current, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            continue  # their loop variables are their own
        stack.extend(ast.iter_child_nodes(current))
    return found


def _is_main_guard(test: ast.expr) -> bool:
    """``__name__ == "__main__"``, either way round."""
    if not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
    ):
        return False
    sides = [test.left, test.comparators[0]]
    has_name = any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides)
    has_main = any(isinstance(s, ast.Constant) and s.value == "__main__" for s in sides)
    return has_name and has_main


def entry_blocks(module: ast.Module) -> list[ast.stmt]:
    """The statements that start the program when the module is run: its
    top-level ``if __name__ == "__main__":`` statements, and each top-level
    statement that is a bare call (``main()`` or ``game.run()`` at the
    bottom of the file, without the guard)."""
    return [
        statement
        for statement in module.body
        if (isinstance(statement, ast.If) and _is_main_guard(statement.test))
        or (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call))
    ]


def entry_calls(module: ast.Module) -> list[ast.Call]:
    """The calls in the module's entry blocks (``entry_blocks``)."""
    return [
        node
        for block in entry_blocks(module)
        for node in ast.walk(block)
        if isinstance(node, ast.Call)
    ]


def imported_names(module: ast.Module) -> dict[str, tuple[str, str]]:
    """``local name -> (module as written, imported name)`` of the module's
    top-level ``from ... import`` statements."""
    found: dict[str, tuple[str, str]] = {}
    for statement in module.body:
        if isinstance(statement, ast.ImportFrom) and statement.module:
            for alias in statement.names:
                found[alias.asname or alias.name] = (statement.module, alias.name)
    return found


def _walk_skipping(root: ast.AST, skip: Sequence[ast.AST]) -> Iterator[ast.AST]:
    stack = [root]
    while stack:
        node = stack.pop()
        if any(node is s for s in skip):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _local_names(
    target: Entity, module: str, tree: ast.Module, modules: Sequence[str]
) -> tuple[set[str], set[str]]:
    """``(names, module aliases)`` code in ``module`` refers to the top-level
    function ``target`` by: its own name in its own module, the local name of
    a ``from <its module> import <it>`` elsewhere; and the local names of its
    module (``import actions``, ``module_aliases``), to be read as
    ``<alias>.<its name>``."""
    simple = target.qualname
    if module == target.module_path:
        return {simple}, set()
    names = {
        local
        for local, (written, original) in imported_names(tree).items()
        if original == simple
        and project_module_by_suffix(written, modules) == target.module_path
    }
    aliases = {
        local
        for local, source in module_aliases(tree, modules).items()
        if source == target.module_path
    }
    return names, aliases


def references_outside(target: Entity, entities: Sequence[Entity]) -> list[str]:
    """The modules where some code outside ``target``'s own body refers to it:
    a name or attribute read (``Load``), a call, a value in a dispatch dict or
    an argument alike. A top-level function is read by the name it has in
    each module (``_local_names``: ``take`` beside it or after ``from actions
    import take``, ``actions.take`` after ``import actions``); anything else,
    a method above all, as any name or attribute spelled as its last name
    segment, since the object it is looked up on is not known. Imports are
    not reads and do not count, nor does code in an entry block
    (``entry_blocks``: an ``if __name__ == "__main__":`` block, a bare call
    at the top of a module): what that block calls is the entry point
    itself, not something an entry point or a dispatcher calls."""
    own = target.extras.get("ast_node")
    simple = name_of(target).rsplit(".", 1)[-1]
    trees = module_nodes(entities)
    modules = [module for module, _ in trees]
    top_level = target.kind == "function" and "." not in target.qualname
    found = []
    for module, tree in trees:
        if top_level:
            names, aliases = _local_names(target, module, tree, modules)
        else:
            names, aliases = {simple}, set()
        skip: list[ast.AST] = list(entry_blocks(tree))
        if own is not None:
            skip.append(own)
        for node in _walk_skipping(tree, skip):
            if not (
                isinstance(node, (ast.Name, ast.Attribute))
                and isinstance(node.ctx, ast.Load)
            ):
                continue
            if isinstance(node, ast.Name):
                hit = node.id in names
            elif top_level:
                hit = (
                    node.attr == simple
                    and isinstance(node.value, ast.Name)
                    and node.value.id in aliases
                )
            else:
                hit = node.attr == simple
            if hit:
                found.append(module)
                break
    return found


def interface_classes(entities: Sequence[Entity]) -> set[str]:
    """The classes that are interfaces (``ast_utils.is_interface``: ``ABC``,
    ``Protocol``, ``ABCMeta``, an ``@abstractmethod``), by name."""
    return {name_of(e) for e, node in classes(entities) if is_interface(node)}


def runnable_method(entity: Entity, node: FunctionNode, interfaces: set[str]) -> bool:
    """Whether a case can run the method on an object of its class: it is
    not abstract (``is_abstract_or_stub``) and its class is no interface, an
    object of which cannot be built."""
    owner = owner_class(entity)
    return (
        owner is not None
        and f"{owner[0]}.{owner[1]}" not in interfaces
        and not is_abstract_or_stub(node)
    )


_TEST_FILES = ("conftest.py",)
_TEST_DIRS = frozenset({"tests", "test"})


def is_test_module(entity: Entity) -> bool:
    """Whether the entity lies in a test of the project: a module named
    ``test_*.py``, ``*_test.py`` or ``conftest.py``, or anything under a
    directory named ``tests`` or ``test``."""
    written = (entity.filepath_rel or "").replace("\\", "/")
    if written:
        path = PurePosixPath(written)
        parts, name = path.parts[:-1], path.name
    else:
        dotted = entity.module_path.split(".")
        parts, name = tuple(dotted[:-1]), dotted[-1] + ".py"
    return (
        name in _TEST_FILES
        or name.startswith("test_")
        or name.endswith("_test.py")
        or any(part in _TEST_DIRS for part in parts)
    )


def project_entities(entities: Sequence[Entity]) -> list[Entity]:
    """``entities`` without those of the project's tests (``is_test_module``):
    a test is no part of the program a principle is about."""
    return [e for e in entities if not is_test_module(e)]


def class_parents(entities: Sequence[Entity]) -> dict[str, list[str]]:
    """The project bases of each class, by name, in the order its class
    statement lists them. A base name is matched to a class of the project by
    its last name segment."""
    every = classes(entities)
    by_simple: dict[str, list[str]] = {}
    for entity, _ in every:
        by_simple.setdefault(entity.qualname.rsplit(".", 1)[-1], []).append(
            name_of(entity)
        )
    parents: dict[str, list[str]] = {}
    for entity, node in every:
        name = name_of(entity)
        for base in node.bases:
            if isinstance(base, ast.Subscript):
                base = base.value  # Generic[T]
            if isinstance(base, ast.Name):
                simple = base.id
            elif isinstance(base, ast.Attribute):
                simple = base.attr
            else:
                continue
            for parent in by_simple.get(simple, []):
                if parent != name and parent not in parents.get(name, []):
                    parents.setdefault(name, []).append(parent)
    return parents


def reachable(start: str, links: Mapping[str, Sequence[str]]) -> set[str]:
    """The names reachable from ``start`` by one or more ``links`` (its
    ancestors by parent links, its descendants by child links), ``start``
    itself never, even on a cycle."""
    found: set[str] = set()
    todo = [start]
    while todo:
        for nxt in links.get(todo.pop(), ()):
            if nxt != start and nxt not in found:
                found.add(nxt)
                todo.append(nxt)
    return found


def class_family(entities: Sequence[Entity]) -> Callable[[str], set[str]]:
    """A function giving the family of a class (by name): the class, its
    project bases and its project subclasses, direct or not
    (``class_parents``)."""
    parents = class_parents(entities)
    children: dict[str, list[str]] = {}
    for name, bases in parents.items():
        for base in bases:
            children.setdefault(base, []).append(name)

    def family(cls: str) -> set[str]:
        return {cls} | reachable(cls, parents) | reachable(cls, children)

    return family


def module_aliases(module: ast.Module, modules: Sequence[str]) -> dict[str, str]:
    """``local name -> project module`` of the module's top-level imports of
    project modules: ``import actions``, ``import actions as a``,
    ``from space_a import actions``, ``from . import actions``. ``import
    space_a.actions`` binds the name ``space_a`` to the package, so it
    stands for the module ``space_a`` only, if the project has it."""
    found: dict[str, str] = {}
    for statement in module.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                # ``import a.b`` binds ``a``, the package: an alias of the
                # module ``a.b`` only with ``as``.
                written = alias.name if alias.asname else alias.name.split(".")[0]
                source = project_module_by_suffix(written, modules)
                if source is not None:
                    found[alias.asname or written] = source
        elif isinstance(statement, ast.ImportFrom):
            prefix = f"{statement.module}." if statement.module else ""
            for alias in statement.names:
                source = project_module_by_suffix(prefix + alias.name, modules)
                if source is not None and source.split(".")[-1] == alias.name:
                    found[alias.asname or alias.name] = source
    return found
