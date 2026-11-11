"""The functions and methods of a module, and what of a function's body
runs as the function runs: its statements outside nested scopes, the
methods it calls on a name, where it first uses an object.
"""

from __future__ import annotations

import ast
from typing import Iterator, Optional

from pythonarchtesting.mutation.project import Module
from pythonarchtesting.mutation.source_edit import alone
from pythonarchtesting.util.ast_utils import dotted, is_docstring, never_runs


def class_methods(
    tree: ast.Module,
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}.{item.name}", item


def module_functions(
    tree: ast.Module,
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """The module-level functions of ``tree``, by name."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node


def parameter_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    arguments = function.args
    return {
        a.arg for a in arguments.posonlyargs + arguments.args + arguments.kwonlyargs
    }


def module_names(tree: ast.Module) -> set[str]:
    """Names bound at module level: imports, classes, functions, globals."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


def first_function(
    tree: ast.Module, text: str
) -> Optional[ast.FunctionDef | ast.AsyncFunctionDef]:
    """The first function whose body starts on a line of its own and runs
    (``never_runs``)."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if never_runs(node):
                continue
            body = node.body
            first = body[1] if is_docstring(body[0]) and len(body) > 1 else body[0]
            if first.lineno > node.lineno and alone(text, first):
                return node
    return None


_SCOPES = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda)


# Code defined in a function that runs only when something calls it (or, for
# a class, has a ``self`` of its own): no place for a mutant of the function.
_NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def outside_scopes(node: ast.AST) -> Iterator[ast.AST]:
    """``ast.walk`` that does not enter comprehensions and lambdas (their
    variables do not exist after the statement) nor nested functions and
    classes (their code does not run where they are defined), except what
    of a nested definition runs where it stands (``_where_defined``)."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        for child in ast.iter_child_nodes(current):
            if isinstance(child, _NESTED):
                stack.extend(_where_defined(child))
            elif not isinstance(child, _SCOPES):
                stack.append(child)


def _where_defined(node: ast.AST) -> list[ast.expr]:
    """What of a nested function, lambda or class runs where it is defined:
    its decorators, a function's or lambda's default values, a class's bases and keywords
    (annotations may never be evaluated, so they are left out)."""
    parts: list[ast.expr] = list(getattr(node, "decorator_list", []))
    if isinstance(node, ast.ClassDef):
        parts += node.bases + [keyword.value for keyword in node.keywords]
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        parts += node.args.defaults + [d for d in node.args.kw_defaults if d]
    return [part for part in parts if not isinstance(part, _SCOPES)]


def body_nodes(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Iterator[ast.AST]:
    """Every node of ``function``'s body that runs as the function runs:
    ``outside_scopes`` of each statement, nested functions and classes
    left out but for what of them runs where they stand (``_where_defined``)."""
    for item in function.body:
        parts = _where_defined(item) if isinstance(item, _NESTED) else [item]
        for part in parts:
            yield from outside_scopes(part)


def _same_name(node: ast.AST, obj: str) -> list[ast.AST]:
    """``node``, or when it is a scope binding a name ``obj`` of its own,
    what of it runs outside that scope."""
    if not isinstance(node, (*_SCOPES, *_NESTED)) or obj not in _bound_in(node):
        return [node]
    if isinstance(node, (*_NESTED, ast.Lambda)):
        return list(_where_defined(node))
    return [node.generators[0].iter]


def _bound_in(scope: ast.AST) -> set[str]:
    """The names a nested scope binds anywhere in it: parameters, and names
    assigned, deleted or used as a loop or comprehension target."""
    return {
        node.arg if isinstance(node, ast.arg) else node.id
        for node in ast.walk(scope)
        if isinstance(node, ast.arg)
        or (isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)))
    }


def called_on(function: ast.FunctionDef | ast.AsyncFunctionDef, obj: str) -> set[str]:
    """The methods ``function`` calls on the name ``obj`` (``obj.m(...)``),
    in a closure too, but not in a nested function, class, comprehension or
    lambda that binds a name ``obj`` of its own (``def inner(obj)``,
    ``[obj.m() for obj in ...]``): that is another object."""
    found: set[str] = set()
    stack = [part for item in function.body for part in _same_name(item, obj)]
    while stack:
        node = stack.pop()
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and dotted(node.func.value) == obj
        ):
            found.add(node.func.attr)
        for child in ast.iter_child_nodes(node):
            stack.extend(_same_name(child, obj))
    return found


SIMPLE = (ast.Expr, ast.Assign, ast.AugAssign, ast.AnnAssign)


def first_method_call(
    module: Module, function: ast.FunctionDef | ast.AsyncFunctionDef, obj: str
) -> Optional[ast.stmt]:
    """The first simple statement of ``function``, on lines of its own, that
    calls a method of ``obj`` (a name, or a module global: ``world.BAG``): a
    statement after it runs under the same condition as that call."""
    statements = sorted(
        (node for node in body_nodes(function) if isinstance(node, SIMPLE)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    for statement in statements:
        if not alone(module.text, statement):
            continue
        if statement.lineno == function.lineno:
            continue  # a one-line function
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and dotted(node.func.value) == obj
            for node in outside_scopes(statement)
        ):
            return statement
    return None


def first_use(
    module: Module, function: ast.FunctionDef | ast.AsyncFunctionDef, obj: str
) -> Optional[ast.stmt]:
    """The first simple statement of ``function``, on lines of its own, that
    calls a method of ``obj`` or else reads it."""
    called = first_method_call(module, function, obj)
    if called is not None:
        return called
    statements = sorted(
        (node for node in body_nodes(function) if isinstance(node, SIMPLE)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    for statement in statements:
        if not alone(module.text, statement):
            continue
        if statement.lineno != function.lineno and any(
            isinstance(node, (ast.Name, ast.Attribute))
            and isinstance(node.ctx, ast.Load)
            and dotted(node) == obj
            for node in outside_scopes(statement)
        ):
            return statement
    return None
