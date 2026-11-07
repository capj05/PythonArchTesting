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
  outside the class must spell it);
- ``add_builtin_call``: ``add_io_call`` generalised to any builtin call an
  error can name: the three I/O calls, ``isinstance(None, (object,)[0])``
  and ``type(None) == object``, a branch on the type (the call is ``member``);
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

A mutant is a whole new text of one file; nothing is written here.
"""

from __future__ import annotations

import ast
import io
import tokenize
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Collection, Iterable, Iterator, Mapping, Optional, Sequence

from pythonarchtesting.execution.import_edges import (
    _resolve_relative_module,
    collect_import_references_from_node,
    normalize_import_reference,
)
from pythonarchtesting.execution.module_structure import module_of

OPERATORS = (
    "add_import",
    "lazy_import",
    "add_library",
    "dynamic_import",
    "rebuild_injected",
    "drop_call",
    "use_private_name",
    "break_port",
    "foreign_write",
    "add_io_call",
    "mutate_private_container",
    "mutate_public_container",
    "stub_role_call",
    "add_io_via_helper",
    "read_private_attribute",
    "add_builtin_call",
    "drop_base",
    "concretize_base",
    "hardcode_collaborator",
)
DEFAULT_LIBRARIES = ("pickle",)
# What the cases of a task say about the parameters of a function:
# ``(file, function) -> {parameter: class name}`` for each parameter a case
# builds a project object for (``$new``). A function listed here gets no
# other parameter's class guessed: its cases show what it is called with.
ParameterClasses = Mapping[tuple[str, str], Mapping[str, str]]
# The constructor parameters a task gives a spy (``{"$spy": ...}`` in its
# ``[init]``): ``(file, class) -> parameter names``.
Spied = Mapping[tuple[str, str], Collection[str]]
# The methods of the builtin containers and of ``str``: a parameter on which
# only these are called may be one of them, so its class is not guessed.
_BUILTIN_METHODS = frozenset(
    name
    for kind in (dict, list, set, str, tuple)
    for name in dir(kind)
    if not name.startswith("_")
)


@dataclass(frozen=True)
class Mutant:
    """One seeded violation: ``file`` (relative) gets the text ``source``.

    ``subject`` is the file whose markers the violation is about: ``file``
    itself, except for ``use_private_name``, which changes a module that
    reaches past another module's interface. ``also`` holds other files the
    mutant changes, as ``(file, source)``.
    """

    id: str
    operator: str
    file: str
    description: str
    source: str
    subject: str = ""
    also: tuple[tuple[str, str], ...] = ()
    imported: str = ""  # what an import operator imports: a module or a library
    # Injection operators: the class, the constructor parameter the
    # collaborator comes in through and, for ``drop_call``, the method no
    # longer called; ``line`` is the changed line, when there is one.
    owner: str = ""
    collaborator: str = ""
    member: str = ""
    line: int = 0
    function: str = ""  # ``Class.method`` the change is in, when one method


@dataclass(frozen=True)
class _Change:
    """What an operator makes: the text of ``file`` and how to describe it."""

    file: str
    description: str
    source: str
    subject: str = ""  # default: ``file``
    also: tuple[tuple[str, str], ...] = ()
    imported: str = ""
    owner: str = ""
    collaborator: str = ""
    member: str = ""
    line: int = 0
    function: str = ""


@dataclass(frozen=True)
class _Module:
    name: str  # dotted, "" for the root package
    file: str  # relative, with "/"
    text: str
    tree: ast.Module
    is_package: bool


def _modules(root: Path) -> list[_Module]:
    modules = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if any(
            part.startswith(".") or part == "__pycache__" for part in relative.parts
        ):
            continue
        parts = list(relative.with_suffix("").parts)
        is_package = parts[-1] == "__init__"
        if is_package:
            parts = parts[:-1]
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        modules.append(
            _Module(".".join(parts), relative.as_posix(), text, tree, is_package)
        )
    return modules


def _imports(module: _Module, names: set[str]) -> set[str]:
    """The project modules ``module`` imports anywhere."""
    found: set[str] = set()
    for ref in collect_import_references_from_node(
        node=module.tree, importer_module=module.name, filepath_rel=module.file
    ):
        for edge in normalize_import_reference(ref):
            target = module_of(edge.imported_module, names)
            if target is not None:
                found.add(target)
    return found


def _import_line(importer: _Module, target: str) -> str:
    """A relative import of the project module ``target`` from ``importer``."""
    depth = len(importer.name.split(".")) if importer.name else 0
    if not importer.is_package:
        depth -= 1
    dots = "." * (depth + 1)
    parent, _, last = target.rpartition(".")
    return f"from {dots}{parent} import {last}"


def _is_future_import(node: ast.stmt) -> bool:
    return isinstance(node, ast.ImportFrom) and node.module == "__future__"


def _header_end(tree: ast.Module) -> int:
    """The 0-based line before which a top-level import goes."""
    body = list(tree.body)
    index = 0
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        index = 1
    while index < len(body) and _is_future_import(body[index]):
        index += 1
    if index < len(body):
        node = body[index]
        decorators = getattr(node, "decorator_list", []) or []
        lines = [int(node.lineno), *(int(d.lineno) for d in decorators)]
        return min(lines) - 1
    last = body[-1] if body else None
    return int(getattr(last, "end_lineno", 0) or 0)


def _insert(text: str, line: int, new: str) -> str:
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    lines.insert(line, new + "\n")
    return "".join(lines)


def _alone(text: str, node: ast.stmt) -> bool:
    """Whether ``node`` has its lines to itself: no header or other statement."""
    lines = text.splitlines()
    first, last = node.lineno - 1, int(node.end_lineno or node.lineno) - 1
    end_col = int(node.end_col_offset or 0)
    before = lines[first][: node.col_offset]
    after = lines[last][end_col:].strip()
    return not before.strip() and (not after or after.startswith("#"))


def _first_function(
    tree: ast.Module, text: str
) -> Optional[ast.FunctionDef | ast.AsyncFunctionDef]:
    """The first function whose body starts on a line of its own."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            first = body[1] if _is_docstring(body[0]) and len(body) > 1 else body[0]
            if first.lineno > node.lineno and _alone(text, first):
                return node
    return None


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _function_insert(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[int, int]:
    """Where a statement goes first in ``function``: 0-based line, indentation."""
    body = function.body
    first = body[0]
    if _is_docstring(first):
        if len(body) > 1:
            return body[1].lineno - 1, body[1].col_offset
        return int(first.end_lineno or first.lineno), first.col_offset
    return first.lineno - 1, first.col_offset


def _add_import(modules: list[_Module], lazy: bool) -> Iterator[_Change]:
    names = {module.name for module in modules}
    for importer in modules:
        imported = _imports(importer, names)
        function = _first_function(importer.tree, importer.text) if lazy else None
        if lazy and function is None:
            continue
        for target in sorted(names):
            if not target or target == importer.name or target in imported:
                continue
            line = _import_line(importer, target)
            who = importer.name or "__init__"
            if lazy and function is not None:
                at, indent = _function_insert(function)
                source = _insert(importer.text, at, " " * indent + line)
                yield _Change(
                    importer.file,
                    f"{who} imports {target} lazily",
                    source,
                    imported=target,
                )
            else:
                at = _header_end(importer.tree)
                yield _Change(
                    importer.file,
                    f"{who} imports {target}",
                    _insert(importer.text, at, line),
                    imported=target,
                )


def _add_library(modules: list[_Module], libraries: Sequence[str]) -> Iterator[_Change]:
    for module in modules:
        if not module.name:
            continue
        for library in libraries:
            used = {
                edge.imported_module.split(".")[0]
                for ref in collect_import_references_from_node(
                    node=module.tree,
                    importer_module=module.name,
                    filepath_rel=module.file,
                )
                for edge in normalize_import_reference(ref)
            }
            if library in used:
                continue
            source = _insert(module.text, _header_end(module.tree), f"import {library}")
            yield _Change(
                module.file,
                f"{module.name} imports {library}",
                source,
                imported=library,
            )


def _dynamic_import(
    modules: list[_Module], libraries: Sequence[str]
) -> Iterator[_Change]:
    """``__import__("<library>")`` at the top of a module's first function: an
    import no static rule sees, run whenever that function runs."""
    for module in modules:
        if not module.name:
            continue
        function = _first_function(module.tree, module.text)
        if function is None:
            continue
        at, indent = _function_insert(function)
        where = _qualname(module.tree, function)
        for library in libraries:
            yield _Change(
                module.file,
                f"{module.name} imports {library} by a computed name in {where}",
                _insert(module.text, at, " " * indent + f'__import__("{library}")'),
                imported=library,
                line=at + 1,
            )


def _qualname(
    tree: ast.Module, function: ast.FunctionDef | ast.AsyncFunctionDef
) -> str:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and function in node.body:
            return f"{node.name}.{function.name}"
    return function.name


def _methods(
    tree: ast.Module,
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}.{item.name}", item


def _self_name(function: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[str]:
    args = function.args.posonlyargs + function.args.args
    return args[0].arg if args else None


def _replace_span(text: str, node: ast.AST, new: str) -> str:
    lines = text.splitlines(keepends=True)
    row = int(getattr(node, "lineno")) - 1
    start, end = int(getattr(node, "col_offset")), int(getattr(node, "end_col_offset"))
    line = lines[row].encode("utf-8")
    lines[row] = (line[:start] + new.encode("utf-8") + line[end:]).decode("utf-8")
    return "".join(lines)


def _kept_names(
    method: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Iterator[tuple[ast.stmt, str, ast.Name]]:
    """Each ``self.x = name`` (also ``self.x: T = name``) in ``method``: the
    statement, the attribute and the name assigned."""
    self_name = _self_name(method)
    for node in ast.walk(method):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target: ast.expr = node.targets[0]
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target = node.target
        else:
            continue
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == self_name
            and isinstance(node.value, ast.Name)
        ):
            yield node, target.attr, node.value


def _kept_parameters(
    method: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Iterator[tuple[ast.stmt, str, ast.Name]]:
    """``_kept_names`` whose name is a parameter of ``method`` (but ``self``)."""
    self_name = _self_name(method)
    params = {
        arg.arg
        for arg in method.args.posonlyargs + method.args.args + method.args.kwonlyargs
    } - {self_name}
    for node, attribute, value in _kept_names(method):
        if value.id in params:
            yield node, attribute, value


def _rebuild_injected(modules: list[_Module]) -> Iterator[_Change]:
    for module in modules:
        for name, method in _methods(module.tree):
            if method.name != "__init__":
                continue
            for node, _, value in _kept_parameters(method):
                if value.lineno != value.end_lineno:
                    continue
                param = value.id
                source = _replace_span(module.text, value, f"type({param})()")
                yield _Change(
                    module.file,
                    f"{module.name}: {name} builds its own {param} (line {node.lineno})",
                    source,
                    owner=name.split(".")[0],
                    collaborator=param,
                    line=node.lineno,
                )


def _collaborator(
    call: ast.Call, self_name: Optional[str], given: frozenset[str] = frozenset()
) -> Optional[tuple[str, str, str]]:
    """``(text, attribute, member)`` when ``call`` is ``self.x.m(...)``
    (``("self.x.m", "x", "m")``), or ``self.x(...)`` with ``x`` among the
    ``given`` attributes, which hold what the constructor was given (a
    function passed in): ``("self.x", "x", "")``."""
    func = call.func
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Attribute)
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == self_name
    ):
        return f"{self_name}.{func.value.attr}.{func.attr}", func.value.attr, func.attr
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == self_name
        and func.attr in given
    ):
        return f"{self_name}.{func.attr}", func.attr, ""
    return None


def _collaborator_call(
    node: ast.stmt, self_name: Optional[str], given: frozenset[str] = frozenset()
) -> Optional[tuple[str, str, str]]:
    """``_collaborator`` of the statement ``node`` when it is only that call."""
    if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
        return None
    return _collaborator(node.value, self_name, given)


def _bypass(text: str, call: ast.Call) -> tuple[str, str]:
    """What a nested collaborator call becomes, and how to say it: its first
    argument passed through (``apply(total)`` -> ``total``), else ``None``."""
    first = call.args[0] if call.args else None
    if first is not None and not isinstance(first, ast.Starred):
        segment = ast.get_source_segment(text, first)
        if segment is not None and "\n" not in segment:
            return segment, "its first argument passed through"
    return "None", "None instead"


def _injected(module: _Module) -> dict[tuple[str, str], str]:
    """``(class, attribute) -> name`` for ``self.a = name`` (or ``self.a: T =
    name``) in a constructor."""
    found: dict[tuple[str, str], str] = {}
    for name, method in _methods(module.tree):
        if method.name != "__init__":
            continue
        for _, attribute, value in _kept_names(method):
            found[(name.split(".")[0], attribute)] = value.id
    return found


def _given(module: _Module) -> set[tuple[str, str]]:
    """``(class, attribute)`` of each attribute a constructor sets to one of
    its parameters: calling it calls what the object was given."""
    return {
        (name.split(".")[0], attribute)
        for name, method in _methods(module.tree)
        if method.name == "__init__"
        for _, attribute, _ in _kept_parameters(method)
    }


def _drop_call(modules: list[_Module]) -> Iterator[_Change]:
    for module in modules:
        injected = _injected(module)
        given_attributes = _given(module)
        for name, method in _methods(module.tree):
            self_name = _self_name(method)
            owner = name.split(".")[0]
            given = frozenset(a for o, a in given_attributes if o == owner)

            def about(
                call: ast.Call,
                found: tuple[str, str, str],
                owner: str = owner,
                name: str = name,
            ) -> dict[str, Any]:
                _, attribute, member = found
                return {
                    "owner": owner,
                    "collaborator": injected.get(
                        (owner, attribute), attribute.lstrip("_")
                    ),
                    "member": member,
                    "line": call.lineno,
                    "function": name,
                }

            found: list[tuple[int, int, _Change]] = []
            statements: set[int] = set()
            for node in ast.walk(method):
                if not isinstance(node, ast.stmt):
                    continue
                collaborator = _collaborator_call(node, self_name, given)
                if collaborator is None:
                    continue
                call = collaborator[0]
                statements.add(id(node.value))  # type: ignore[attr-defined]
                if not _alone(module.text, node):
                    continue  # sharing its line, it cannot be cut out cleanly
                lines = module.text.splitlines(keepends=True)
                first, last = node.lineno - 1, int(node.end_lineno or node.lineno)
                lines[first:last] = [" " * node.col_offset + "pass\n"]
                found.append(
                    (
                        node.lineno,
                        node.col_offset,
                        _Change(
                            module.file,
                            f"{module.name}: {name} no longer calls {call} "
                            f"(line {node.lineno})",
                            "".join(lines),
                            **about(
                                node.value,  # type: ignore[attr-defined]
                                collaborator,
                            ),
                        ),
                    )
                )
            # A call whose result is used (``x = self.d.apply(x)``): the
            # collaborator is bypassed, its argument taken as the result.
            for node in ast.walk(method):
                if not isinstance(node, ast.Call) or id(node) in statements:
                    continue
                collaborator = _collaborator(node, self_name, given)
                if collaborator is None or node.lineno != node.end_lineno:
                    continue
                call = collaborator[0]
                replacement, how = _bypass(module.text, node)
                found.append(
                    (
                        node.lineno,
                        node.col_offset,
                        _Change(
                            module.file,
                            f"{module.name}: {name} no longer calls {call} "
                            f"(line {node.lineno}, {how})",
                            _replace_span(module.text, node, replacement),
                            **about(node, collaborator),
                        ),
                    )
                )
            for _, _, change in sorted(found, key=lambda item: item[:2]):
                yield change


PRIVATE_HELPER = "_archtest_private"


def _use_private_name(
    modules: list[_Module],
) -> Iterator[_Change]:
    for owner in modules:
        helper = (
            owner.text.rstrip("\n")
            + f"\n\n\ndef {PRIVATE_HELPER}():\n    return None\n"
        )
        for importer in modules:
            if importer.name == owner.name:
                continue
            line = f"from {_relative(importer, owner.name)} import {PRIVATE_HELPER}"
            source = _insert(importer.text, _header_end(importer.tree), line)
            function = _first_function(ast.parse(source), source)
            if function is not None:
                # Called where the module's code runs, so a run sees it too.
                at, indent = _function_insert(function)
                source = _insert(source, at, " " * indent + f"{PRIVATE_HELPER}()")
            who = importer.name or "__init__"
            yield _Change(
                importer.file,
                f"{who} calls a private helper of {owner.name or '__init__'}",
                source,
                subject=owner.file,
                also=((owner.file, helper),),
            )


def _relative(importer: _Module, target: str) -> str:
    """``target`` spelled relatively from ``importer`` (``.models``, ``..pkg.x``)."""
    depth = len(importer.name.split(".")) if importer.name else 0
    if not importer.is_package:
        depth -= 1
    return "." * (depth + 1) + target


def _public_methods(
    tree: ast.Module, text: str
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Public methods of top-level classes whose body starts on its own line."""
    for name, method in _methods(tree):
        if method.name.startswith("_"):
            continue
        if method.body[0].lineno <= method.lineno or not _alone(text, method.body[0]):
            continue
        yield name, method


def _header(method: ast.FunctionDef | ast.AsyncFunctionDef, indent: int) -> str:
    """The ``def`` line(s) of ``method`` as Python writes them, without decorators."""
    bare = ast.FunctionDef(
        name=method.name,
        args=method.args,
        body=[ast.Pass()],
        decorator_list=[],
        returns=method.returns,
        type_comment=None,
    )
    if hasattr(method, "type_params"):
        setattr(bare, "type_params", getattr(method, "type_params"))
    node: ast.FunctionDef | ast.AsyncFunctionDef = bare
    if isinstance(method, ast.AsyncFunctionDef):
        node = ast.AsyncFunctionDef(**{f: getattr(bare, f) for f in bare._fields})
    ast.fix_missing_locations(node)
    lines = ast.unparse(node).splitlines()[:-1]  # drop the "pass"
    return "".join(" " * indent + line + "\n" for line in lines)


def _break_port(modules: list[_Module]) -> Iterator[_Change]:
    import copy

    for module in modules:
        for name, method in _public_methods(module.tree, module.text):
            lines = module.text.splitlines(keepends=True)
            first, body = method.lineno - 1, method.body[0].lineno - 1
            indent = method.col_offset
            args = copy.deepcopy(method.args)
            required = len(args.args) - len(args.defaults)
            args.args.insert(required, ast.arg(arg="extra"))
            changed = copy.copy(method)
            changed.args = args
            yield _Change(
                module.file,
                f"{module.name}: {name} takes a new required parameter",
                "".join(lines[:first] + [_header(changed, indent)] + lines[body:]),
            )
            renamed = copy.copy(method)
            renamed.name = f"{method.name}_renamed"
            yield _Change(
                module.file,
                f"{module.name}: {name} is renamed",
                "".join(lines[:first] + [_header(renamed, indent)] + lines[body:]),
            )


_SIMPLE = (ast.Expr, ast.Assign, ast.AugAssign, ast.AnnAssign)


def _module_names(tree: ast.Module) -> set[str]:
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


def _functions(
    tree: ast.Module,
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """The module-level functions of ``tree``, by name."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node


def _parameters(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    arguments = function.args
    return {
        a.arg for a in arguments.posonlyargs + arguments.args + arguments.kwonlyargs
    }


def _annotated_class(annotation: Optional[ast.expr]) -> Optional[str]:
    """The class name a parameter's annotation names (``Inventory``,
    ``inventory.Inventory``, ``"Inventory"``), else ``None``."""
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        name = annotation.value.rpartition(".")[2]
        return name if name.isidentifier() else None
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Attribute):
        return annotation.attr
    return None


def _data_attributes(classes: list[ast.ClassDef]) -> list[str]:
    """The data attributes of a project class: its annotated class-level
    fields and what its methods assign to ``self.<name>`` (in an unpacking
    too); never a method."""
    if len(classes) != 1:
        return []  # no class of that name in the project, or several
    (cls,) = classes
    methods = {
        n.name
        for n in cls.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    found: list[str] = []
    for node in cls.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found.append(node.target.id)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self_name = _self_name(node)
            # Every attribute of self assigned to, also inside an unpacking
            # (``self.x, self.y = v``) or a for/with target.
            found += [
                item.attr
                for item in ast.walk(node)
                if isinstance(item, ast.Attribute)
                and isinstance(item.ctx, ast.Store)
                and isinstance(item.value, ast.Name)
                and item.value.id == self_name
            ]
    return [a for a in dict.fromkeys(found) if a not in methods]


def mangled(owner: str, attribute: str) -> str:
    """``attribute`` as code outside class ``owner`` reads it: a private
    ``__x`` is stored as ``_Owner__x``; any other name stays."""
    if attribute.startswith("__") and not attribute.endswith("__"):
        return f"_{owner.lstrip('_')}{attribute}"
    return attribute


def _private(attribute: str) -> bool:
    return attribute.startswith("_") and not (
        attribute.startswith("__") and attribute.endswith("__")
    )


@dataclass
class _Use:
    """How a function uses an object it did not get as ``self``."""

    first: ast.stmt  # the first statement that reads it
    change: Optional[ast.stmt] = None  # the first ``x.method(...)`` statement
    reads: list[str] = field(default_factory=list)  # data attributes it reads


def _uses(
    module: _Module,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    skip: set[str],
) -> dict[str, _Use]:
    """The objects ``function`` reads attributes of, in order of first use
    in a simple statement (where a write can follow); their data attributes
    are those it reads anywhere in its body (an ``if`` test too) without
    calling them."""
    everywhere = [node for item in function.body for node in _outside_scopes(item)]
    called_anywhere = {id(n.func) for n in everywhere if isinstance(n, ast.Call)}
    data: dict[str, list[str]] = {}
    for node in sorted(
        (
            n
            for n in everywhere
            if isinstance(n, ast.Attribute)
            and isinstance(n.ctx, ast.Load)
            and isinstance(n.value, ast.Name)
            and id(n) not in called_anywhere
        ),
        key=lambda n: (n.lineno, n.col_offset),
    ):
        attrs = data.setdefault(node.value.id, [])  # type: ignore[attr-defined]
        if node.attr not in attrs:
            attrs.append(node.attr)
    uses: dict[str, _Use] = {}
    statements = sorted(
        (node for node in ast.walk(function) if isinstance(node, _SIMPLE)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    for statement in statements:
        if statement.lineno == function.lineno or not _alone(module.text, statement):
            continue  # a one-line function, or a statement sharing its line
        nodes = list(_outside_scopes(statement))
        called = {id(n.func) for n in nodes if isinstance(n, ast.Call)}
        reads = sorted(
            (
                node
                for node in nodes
                if isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and isinstance(node.value, ast.Name)
                and node.value.id not in skip
            ),
            key=lambda node: (node.lineno, node.col_offset),
        )
        for read in reads:
            obj = read.value.id  # type: ignore[attr-defined]
            use = uses.setdefault(obj, _Use(statement, reads=list(data.get(obj, []))))
            if id(read) in called and (
                use.change is None
                and isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Call)
                and statement.value.func is read
            ):
                use.change = statement
    return uses


def _foreign_write(
    modules: list[_Module], hints: Optional[ParameterClasses] = None
) -> Iterator[_Change]:
    """``x.a = x.a`` in a method on an object it did not get as ``self`` (in
    a module-level function: on an object it got as a parameter). The value
    stays, but another object's data attribute is assigned from outside its
    class: ``a`` is never a method the code calls, and a private attribute
    (``_stock``) is preferred, among the attributes the function reads and,
    for a parameter annotated with a project class, the data attributes of
    that class. The write follows the first statement that calls a method of
    ``x`` for its effect (``x.remove(...)``), so it runs under the same
    condition as that state change; without one, it follows the first
    statement that reads ``x``."""
    classes: dict[str, list[ast.ClassDef]] = {}
    for module in modules:
        for node in module.tree.body:
            if isinstance(node, ast.ClassDef):
                classes.setdefault(node.name, []).append(node)
    for module in modules:
        skip = _module_names(module.tree)
        callables = [
            (name, method, _self_name(method), None)
            for name, method in _methods(module.tree)
        ] + [
            (name, function, None, _parameters(function))
            for name, function in _functions(module.tree)
        ]
        for name, function, self_name, only in callables:
            arguments = function.args
            hinted = None if hints is None else hints.get((module.file, name))
            annotated = {
                a.arg: (
                    hinted.get(a.arg)
                    if hinted is not None
                    else _annotated_class(a.annotation)
                )
                for a in arguments.posonlyargs + arguments.args + arguments.kwonlyargs
            }
            uses = _uses(module, function, {*skip, *([self_name] if self_name else [])})
            for obj, use in uses.items():
                if only is not None and obj not in only:
                    continue
                owner_class = annotated.get(obj)
                # A name-mangled ``__x`` of the class is ``_Owner__x`` outside it.
                candidates = use.reads + [
                    mangled(owner_class or "", a)
                    for a in _data_attributes(classes.get(owner_class or "", []))
                    if a not in use.reads
                ]
                if not candidates:
                    continue  # only methods of it are used: nothing to replace
                attribute = next((a for a in candidates if _private(a)), candidates[0])
                target = f"{obj}.{attribute}"
                at = use.change or use.first
                line = int(at.end_lineno or at.lineno)
                source = _insert(
                    module.text, line, " " * at.col_offset + f"{target} = {target}"
                )
                yield _Change(
                    module.file,
                    f"{module.name}: {name} writes {target} (line {line + 1})",
                    source,
                    owner=name.split(".")[0] if self_name is not None else "",
                    line=line + 1,
                    function=name,
                )


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
    "type": ["type(None) == object"],
}


def _add_io_call(
    modules: list[_Module], calls: Mapping[str, list[str]] = IO_CALLS
) -> Iterator[_Change]:
    """Each function and method first calls ``print``, ``input`` or ``open``
    (by default): output, keyboard input or file access in code that should
    have none; with ``BUILTIN_CALLS`` also ``isinstance()`` and ``type()``."""
    for module in modules:
        callables = list(_methods(module.tree)) + list(_functions(module.tree))
        for name, function in sorted(callables, key=lambda item: item[1].lineno):
            if function.body[0].lineno == function.lineno:
                continue  # a one-line function has no room for it
            at, indent = _function_insert(function)
            for member, lines in calls.items():
                yield _Change(
                    module.file,
                    f"{module.name}: {name} calls {member}() (line {at + 1})",
                    _insert(
                        module.text, at, "\n".join(" " * indent + x for x in lines)
                    ),
                    member=member,
                    line=at + 1,
                    function=name,
                )


# What a container the owner's constructor creates is, by its first value.
_CONTAINER_CALLS = ("dict", "list", "set")
# The statement that changes a container's contents, by its kind.
CONTAINER_FILLS = {
    "dict": '{target}["__archtest__"] = 0',
    "list": "{target}.append(0)",
    "set": "{target}.add(0)",
}


# Library classes that build a dict.
_DICT_CALLS = ("defaultdict", "Counter", "OrderedDict")


def _call_name(func: ast.expr) -> Optional[str]:
    """``dict`` of ``dict(...)``, ``defaultdict`` of ``collections.defaultdict(...)``."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _container_kind(value: Optional[ast.expr]) -> Optional[str]:
    """``dict``, ``list`` or ``set`` when ``value`` builds one: a display
    (``{}``, ``[]``, ``{1}``), a comprehension, ``dict(...)``, ``list(...)``,
    ``set(...)``, ``defaultdict(...)``, ``Counter(...)``, ``OrderedDict(...)``,
    or a choice one of whose branches does (``x if x is not None else {}``,
    ``x or []``) and none of which is a constant (``[] if x else None`` may
    leave no container); else ``None``."""
    if isinstance(value, (ast.Dict, ast.DictComp)):
        return "dict"
    if isinstance(value, (ast.List, ast.ListComp)):
        return "list"
    if isinstance(value, (ast.Set, ast.SetComp)):
        return "set"
    if isinstance(value, ast.Call):
        name = _call_name(value.func)
        if name in _CONTAINER_CALLS:
            return name
        if name in _DICT_CALLS:
            return "dict"
        return None
    branches: list[ast.expr] = []
    if isinstance(value, ast.IfExp):
        branches = [value.body, value.orelse]
    elif isinstance(value, ast.BoolOp):
        branches = list(value.values)
    if any(isinstance(branch, ast.Constant) for branch in branches):
        return None
    kinds = {_container_kind(branch) for branch in branches} - {None}
    return kinds.pop() if len(kinds) == 1 else None


def _is_dataclass(cls: ast.ClassDef) -> bool:
    return any(
        _call_name(d.func if isinstance(d, ast.Call) else d) == "dataclass"
        for d in cls.decorator_list
    )


def _field_factory(value: Optional[ast.expr]) -> Optional[str]:
    """``dict``, ``list`` or ``set`` of ``field(default_factory=dict)``."""
    if not (isinstance(value, ast.Call) and _call_name(value.func) == "field"):
        return None
    for keyword in value.keywords:
        if keyword.arg == "default_factory" and isinstance(keyword.value, ast.Name):
            factory = keyword.value.id
            if factory in _CONTAINER_CALLS:
                return factory
            if factory in _DICT_CALLS:
                return "dict"
    return None


def _containers(cls: ast.ClassDef) -> dict[str, str]:
    """``attribute -> kind`` for the containers ``__init__`` assigns to
    ``self`` (of a ``@dataclass``, also its fields with a container
    ``default_factory``), in the order it assigns them. An attribute any method of the
    class assigns anything else (a tuple, ``None``) is no container: changing
    its contents could break the class itself."""
    methods = _method_names(cls)
    found: list[tuple[int, int, str, str, Optional[str]]] = []
    if _is_dataclass(cls):
        # A field the generated ``__init__`` fills from its default factory.
        found += [
            (node.lineno, node.col_offset, "__init__", node.target.id, kind)
            for node in cls.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and (kind := _field_factory(node.value)) is not None
        ]
    for node in cls.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        self_name = _self_name(node)
        for item in ast.walk(node):
            if isinstance(item, ast.Assign):
                targets, value = list(item.targets), item.value
            elif isinstance(item, ast.AnnAssign) and item.value is not None:
                targets, value = [item.target], item.value
            else:
                continue
            found += [
                (
                    item.lineno,
                    item.col_offset,
                    node.name,
                    t.attr,
                    _container_kind(value),
                )
                for t in targets
                if isinstance(t, ast.Attribute)
                and isinstance(t.value, ast.Name)
                and t.value.id == self_name
            ]
    kinds: dict[str, set[Optional[str]]] = {}
    initial: dict[str, str] = {}
    for _, _, method, attribute, kind in sorted(found, key=lambda f: f[:2]):
        kinds.setdefault(attribute, set()).add(kind)
        if method == "__init__" and kind is not None:
            initial.setdefault(attribute, kind)
    return {a: k for a, k in initial.items() if kinds[a] == {k} and a not in methods}


def _method_names(cls: ast.ClassDef) -> set[str]:
    return {
        n.name
        for n in cls.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _called_on(function: ast.FunctionDef | ast.AsyncFunctionDef, obj: str) -> set[str]:
    """The methods ``function`` calls on the name ``obj`` (``obj.m(...)``)."""
    return {
        node.func.attr
        for item in function.body
        for node in ast.walk(item)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == obj
    }


def _first_method_call(
    module: _Module, function: ast.FunctionDef | ast.AsyncFunctionDef, obj: str
) -> Optional[ast.stmt]:
    """The first simple statement of ``function``, on lines of its own, that
    calls a method of ``obj``: a statement after it runs under the same
    condition as that call."""
    statements = sorted(
        (node for item in function.body for node in ast.walk(item)),
        key=lambda node: (getattr(node, "lineno", 0), getattr(node, "col_offset", 0)),
    )
    for statement in statements:
        if not isinstance(statement, _SIMPLE) or not _alone(module.text, statement):
            continue
        if statement.lineno == function.lineno:
            continue  # a one-line function
        if any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == obj
            for node in _outside_scopes(statement)
        ):
            return statement
    return None


def _owner_class(
    classes: dict[str, list[ast.ClassDef]],
    annotation: Optional[ast.expr],
    called: set[str],
    hints: Optional[Mapping[str, str]] = None,
    parameter: str = "",
) -> Optional[ast.ClassDef]:
    """The project class of a parameter. With ``hints`` (what a task's cases
    build for the function's parameters, ``ParameterClasses``), the class
    they build for it, and none for a parameter they build no project object
    for. Without, the one its annotation names; for a parameter without one,
    the one project class that has every method called on it, unless each of
    those is also a method of a builtin container or ``str`` (a ``dict``
    whose ``items()`` is called is no project object)."""
    if hints is not None:
        hinted = classes.get(hints.get(parameter, ""), [])
        return hinted[0] if len(hinted) == 1 else None
    named = classes.get(_annotated_class(annotation) or "", [])
    if len(named) == 1:
        return named[0]
    if annotation is not None or not called or called <= _BUILTIN_METHODS:
        return None
    fitting = [
        cls
        for found in classes.values()
        for cls in found
        if called <= _method_names(cls)
    ]
    return fitting[0] if len(fitting) == 1 else None


def _mutate_container(
    modules: list[_Module], private: bool, hints: Optional[ParameterClasses] = None
) -> Iterator[_Change]:
    """Right after the first statement of a client function that calls a
    method of an object of a project class (a parameter, never ``self``),
    the function changes the contents of that object's first private (or
    public) container: a key in a dict, an item appended to a list or added
    to a set. A method of the class itself is no client."""
    classes: dict[str, list[ast.ClassDef]] = {}
    for module in modules:
        for node in module.tree.body:
            if isinstance(node, ast.ClassDef):
                classes.setdefault(node.name, []).append(node)
    for module in modules:
        callables = [
            (name, method, _self_name(method)) for name, method in _methods(module.tree)
        ] + [(name, function, None) for name, function in _functions(module.tree)]
        for name, function, self_name in sorted(callables, key=lambda c: c[1].lineno):
            arguments = function.args
            for arg in arguments.posonlyargs + arguments.args + arguments.kwonlyargs:
                if arg.arg == self_name:
                    continue
                cls = _owner_class(
                    classes,
                    arg.annotation,
                    _called_on(function, arg.arg),
                    None if hints is None else hints.get((module.file, name)),
                    arg.arg,
                )
                if cls is None or (
                    self_name is not None and cls.name == name.split(".")[0]
                ):
                    continue
                attributes = [
                    (a, kind)
                    for a, kind in _containers(cls).items()
                    if (_private(a) if private else not a.startswith("_"))
                ]
                statement = _first_method_call(module, function, arg.arg)
                if not attributes or statement is None:
                    continue
                attribute, kind = attributes[0]
                attribute = mangled(cls.name, attribute)
                target = f"{arg.arg}.{attribute}"
                line = int(statement.end_lineno or statement.lineno)
                fill = CONTAINER_FILLS[kind].format(target=target)
                yield _Change(
                    module.file,
                    f"{module.name}: {name} changes the contents of {target} "
                    f"(line {line + 1})",
                    _insert(module.text, line, " " * statement.col_offset + fill),
                    owner=cls.name,
                    member=attribute,
                    line=line + 1,
                    function=name,
                )


def _top_functions(module: _Module) -> set[str]:
    return {name for name, _ in _functions(module.tree)}


def _project_callables(
    module: _Module, by_name: dict[str, _Module]
) -> tuple[dict[str, str], dict[str, str]]:
    """What names in ``module`` stand for: ``name -> project module`` of the
    top-level functions it defines or imports (``from .grades import *``
    imports the public ones), and of the project modules it imports
    (``from . import tools``, ``import tools as t``)."""
    functions = {name: module.name for name in _top_functions(module)}
    aliases: dict[str, str] = {}
    for node in ast.walk(module.tree):
        if isinstance(node, ast.ImportFrom):
            base = (
                _resolve_relative_module(
                    importer_module=module.name,
                    filepath_rel=module.file,
                    level=node.level,
                    module=node.module,
                )
                if node.level
                else node.module or ""
            )
            for alias in node.names:
                if alias.name == "*":
                    # ``from .grades import *``: its public top-level functions.
                    if base in by_name:
                        for star in sorted(_top_functions(by_name[base])):
                            if not star.startswith("_"):
                                functions.setdefault(star, base)
                    continue
                bound = alias.asname or alias.name
                full = f"{base}.{alias.name}" if base else alias.name
                if full in by_name:
                    aliases[bound] = full
                elif base in by_name and alias.name in _top_functions(by_name[base]):
                    functions[bound] = base
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in by_name and (alias.asname or "." not in alias.name):
                    aliases[alias.asname or alias.name] = alias.name
    return functions, aliases


def _replace_spans(text: str, nodes: list[ast.expr], new: str) -> str:
    """``text`` with each one-line node in ``nodes`` replaced by ``new``."""
    lines = text.splitlines(keepends=True)
    for node in sorted(nodes, key=lambda n: (n.lineno, n.col_offset), reverse=True):
        row = node.lineno - 1
        start, end = node.col_offset, int(node.end_col_offset or 0)
        line = lines[row].encode("utf-8")
        lines[row] = (line[:start] + new.encode("utf-8") + line[end:]).decode("utf-8")
    return "".join(lines)


STUB = "(lambda *a, **k: None)"


def _stub_role_call(modules: list[_Module]) -> Iterator[_Change]:
    """A function or method calls no function of one project module any
    more: each such call's function becomes ``(lambda *a, **k: None)``, its
    arguments still evaluated. One mutant per function and module
    (``member``); ``prepare_task`` keeps those of a module the check names."""
    by_name = {module.name: module for module in modules}
    for module in modules:
        functions, aliases = _project_callables(module, by_name)
        callables = list(_methods(module.tree)) + list(_functions(module.tree))
        for name, function in sorted(callables, key=lambda item: item[1].lineno):
            calls: dict[str, list[ast.expr]] = {}
            for item in function.body:
                for node in ast.walk(item):
                    if not isinstance(node, ast.Call):
                        continue
                    func = node.func
                    target = None
                    if isinstance(func, ast.Name):
                        target = functions.get(func.id)
                    elif (
                        isinstance(func, ast.Attribute)
                        and isinstance(func.value, ast.Name)
                        and func.value.id in aliases
                        and func.attr in _top_functions(by_name[aliases[func.value.id]])
                    ):
                        target = aliases[func.value.id]
                    if target is not None and func.lineno == func.end_lineno:
                        calls.setdefault(target, []).append(func)
            for target, funcs in sorted(calls.items()):
                line = min(func.lineno for func in funcs)
                yield _Change(
                    module.file,
                    f"{module.name}: {name} no longer calls into "
                    f"{target or '__init__'} (line {line})",
                    _replace_spans(module.text, funcs, STUB),
                    member=target,
                    line=line,
                    function=name,
                )


HELPER_MODULE = "_archtest_helper"
HELPER_SOURCE = "def say(*args):\n    print(*args)\n"


def _add_io_via_helper(modules: list[_Module]) -> Iterator[_Change]:
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
        spelled = _relative(module, HELPER_MODULE) if "" in names else HELPER_MODULE
        callables = list(_methods(module.tree)) + list(_functions(module.tree))
        for name, function in sorted(callables, key=lambda item: item[1].lineno):
            if function.body[0].lineno == function.lineno:
                continue  # a one-line function has no room for it
            if any(
                isinstance(node, ast.Name) and node.id == "say"
                for node in ast.walk(function)
            ):
                continue  # the import would shadow a name the function uses
            at, indent = _function_insert(function)
            line = f'from {spelled} import say; say("archtest")'
            yield _Change(
                module.file,
                f"{module.name}: {name} prints through {HELPER_MODULE}.say "
                f"(line {at + 1})",
                _insert(module.text, at, " " * indent + line),
                also=((helper, HELPER_SOURCE),),
                member="print",
                line=at + 1,
                function=name,
            )


def _read_private_attribute(
    modules: list[_Module], hints: Optional[ParameterClasses] = None
) -> Iterator[_Change]:
    """A client function (or a method of another class) reads the first
    private data attribute of an object of a project class it got as a
    parameter, first thing: ``_ = obj._x``. Nothing else changes, so the
    mutant runs as the reference does. A function that uses the name ``_``
    itself, or has its body on the ``def`` line, gives none."""
    classes: dict[str, list[ast.ClassDef]] = {}
    for module in modules:
        for node in module.tree.body:
            if isinstance(node, ast.ClassDef):
                classes.setdefault(node.name, []).append(node)
    for module in modules:
        callables = [
            (name, method, _self_name(method)) for name, method in _methods(module.tree)
        ] + [(name, function, None) for name, function in _functions(module.tree)]
        for name, function, self_name in sorted(callables, key=lambda c: c[1].lineno):
            if function.body[0].lineno == function.lineno or any(
                isinstance(node, ast.Name) and node.id == "_"
                for node in ast.walk(function)
            ):
                continue
            arguments = function.args
            for arg in arguments.posonlyargs + arguments.args + arguments.kwonlyargs:
                if arg.arg == self_name:
                    continue
                cls = _owner_class(
                    classes,
                    arg.annotation,
                    _called_on(function, arg.arg),
                    None if hints is None else hints.get((module.file, name)),
                    arg.arg,
                )
                if cls is None or (
                    self_name is not None and cls.name == name.split(".")[0]
                ):
                    continue
                private = [a for a in _data_attributes([cls]) if _private(a)]
                if not private:
                    continue
                attribute = mangled(cls.name, private[0])
                target = f"{arg.arg}.{attribute}"
                at, indent = _function_insert(function)
                yield _Change(
                    module.file,
                    f"{module.name}: {name} reads {target} (line {at + 1})",
                    _insert(module.text, at, " " * indent + f"_ = {target}"),
                    owner=cls.name,
                    member=attribute,
                    line=at + 1,
                    function=name,
                )
                break  # one object per function


def _base_list(text: str, cls: ast.ClassDef) -> Optional[tuple[int, int]]:
    """Character offsets of the ``(`` of ``cls``'s list of bases and of the
    character after its ``)``; ``None`` when the header has none."""
    lines = text.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))
    first = cls.lineno - 1

    def offset(row: int, col: int) -> int:
        return starts[first + row - 1] + col

    depth = 0
    opened: Optional[int] = None
    tokens = tokenize.generate_tokens(io.StringIO("".join(lines[first:])).readline)
    for token in tokens:
        if token.type != tokenize.OP:
            continue
        if token.string in "([{":
            if depth == 0 and token.string == "(":
                opened = offset(*token.start)
            depth += 1
        elif token.string in ")]}":
            depth -= 1
            if depth == 0 and opened is not None:
                return opened, offset(*token.end)
        elif token.string == ":" and depth == 0:
            return None
    return None


def _with_bases(text: str, cls: ast.ClassDef, kept: list[ast.AST]) -> Optional[str]:
    """``text`` with ``cls``'s list of bases and keywords cut down to ``kept``."""
    span = _base_list(text, cls)
    if span is None:
        return None
    parts = [ast.get_source_segment(text, node) for node in kept]
    if any(part is None for part in parts):
        return None
    new = f"({', '.join(str(part) for part in parts)})" if parts else ""
    return text[: span[0]] + new + text[span[1] :]


def _classes(module: _Module) -> Iterator[ast.ClassDef]:
    for node in module.tree.body:
        if isinstance(node, ast.ClassDef):
            yield node


def _drop_base(modules: list[_Module]) -> Iterator[_Change]:
    """A top-level class no longer names one of its bases, ``object``
    excepted: one mutant per class and base; keywords stay."""
    for module in modules:
        for cls in _classes(module):
            for base in cls.bases:
                name = ast.unparse(base)
                if name == "object":
                    continue
                kept: list[ast.AST] = [b for b in cls.bases if b is not base]
                source = _with_bases(module.text, cls, kept + list(cls.keywords))
                if source is None:
                    continue
                yield _Change(
                    module.file,
                    f"{module.name}: {cls.name} no longer derives from {name} "
                    f"(line {cls.lineno})",
                    source,
                    owner=cls.name,
                    member=name,
                    line=cls.lineno,
                    function=cls.name,
                )


# What makes a class abstract by its own code: a base, a metaclass, a
# decorator of a method (as ``ast.unparse`` spells them; a generic
# ``Protocol[T]`` by its value).
ABSTRACT_BASES = frozenset(
    {"ABC", "abc.ABC", "Protocol", "typing.Protocol", "typing_extensions.Protocol"}
)
ABSTRACT_METACLASSES = frozenset({"ABCMeta", "abc.ABCMeta"})
ABSTRACT_DECORATORS = frozenset(
    prefix + name
    for prefix in ("", "abc.")
    for name in (
        "abstractmethod",
        "abstractproperty",
        "abstractclassmethod",
        "abstractstaticmethod",
    )
)


def _abstract_base(base: ast.expr) -> bool:
    node = base.value if isinstance(base, ast.Subscript) else base
    return ast.unparse(node) in ABSTRACT_BASES


def _concretize_base(modules: list[_Module]) -> Iterator[_Change]:
    """An abstract top-level class becomes an ordinary one: ``ABC`` and
    ``Protocol`` leave its bases, ``metaclass=ABCMeta`` its keywords and
    ``@abstractmethod`` (on lines of its own) its methods. The imports stay.
    A class with none of these gives no mutant."""
    for module in modules:
        for cls in _classes(module):
            bases = [b for b in cls.bases if not _abstract_base(b)]
            keywords = [
                k
                for k in cls.keywords
                if not (
                    k.arg == "metaclass"
                    and ast.unparse(k.value) in ABSTRACT_METACLASSES
                )
            ]
            decorators = [
                decorator
                for item in cls.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                for decorator in item.decorator_list
                if ast.unparse(decorator) in ABSTRACT_DECORATORS
            ]
            removed = [ast.unparse(b) for b in cls.bases if b not in bases] + [
                ast.unparse(k) for k in cls.keywords if k not in keywords
            ]
            if not removed and not decorators:
                continue
            lines = module.text.splitlines(keepends=True)
            for decorator in sorted(decorators, key=lambda d: d.lineno, reverse=True):
                del lines[decorator.lineno - 1 : int(decorator.end_lineno or 0)]
            source = "".join(lines)
            if removed:
                rewritten = _with_bases(source, cls, [*bases, *keywords])
                if rewritten is None:
                    continue
                source = rewritten
            removed += ["@" + ast.unparse(d) for d in decorators]
            yield _Change(
                module.file,
                f"{module.name}: {cls.name} is no longer abstract, without "
                f"{', '.join(dict.fromkeys(removed))} (line {cls.lineno})",
                source,
                owner=cls.name,
                line=cls.lineno,
                function=cls.name,
            )


def _abstract(cls: ast.ClassDef) -> bool:
    """Whether ``cls`` is abstract by its own code (a base, a metaclass, an
    abstract method): such a class cannot be built."""
    return (
        any(_abstract_base(base) for base in cls.bases)
        or any(
            k.arg == "metaclass" and ast.unparse(k.value) in ABSTRACT_METACLASSES
            for k in cls.keywords
        )
        or any(
            ast.unparse(decorator) in ABSTRACT_DECORATORS
            for item in cls.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            for decorator in item.decorator_list
        )
    )


def _required_parameters(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether a constructor has a parameter without a default, ``self`` aside."""
    args = function.args
    positional = len(args.posonlyargs) + len(args.args) - 1
    return positional > len(args.defaults) or any(d is None for d in args.kw_defaults)


def _required_field(item: ast.stmt) -> bool:
    """Whether a dataclass body statement is a field without a default."""
    if not (isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)):
        return False
    if "ClassVar" in ast.unparse(item.annotation):
        return False
    value = item.value
    if value is None:
        return True
    return (
        isinstance(value, ast.Call)
        and _call_name(value.func) == "field"
        and not any(k.arg in ("default", "default_factory") for k in value.keywords)
    )


# Bases that add no constructor parameters.
_PLAIN_BASES = ABSTRACT_BASES | {"object", "Generic", "typing.Generic"}


def _needs_arguments(
    cls: ast.ClassDef, classes: Mapping[str, ast.ClassDef], seen: frozenset[str]
) -> Optional[bool]:
    """Whether building ``cls`` needs arguments: its own ``__init__``, its
    dataclass fields, else the first project base that decides; ``None`` when
    a base is no project class the operator knows."""
    for item in cls.body:
        if (
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == "__init__"
        ):
            return _required_parameters(item)
    if _is_dataclass(cls):
        return _required_fields(cls, classes, seen)
    for base in cls.bases:
        name = ast.unparse(base.value if isinstance(base, ast.Subscript) else base)
        if name in _PLAIN_BASES:
            continue
        parent = classes.get(name.rpartition(".")[2])
        if parent is None or parent.name in seen:
            return None
        decided = _needs_arguments(parent, classes, seen | {parent.name})
        if decided is not False:
            return decided
    return False


def _project_bases(
    cls: ast.ClassDef, classes: Mapping[str, ast.ClassDef], seen: frozenset[str]
) -> Iterator[ast.ClassDef]:
    """The project classes ``cls`` names as its bases, by their last name."""
    for base in cls.bases:
        name = ast.unparse(base.value if isinstance(base, ast.Subscript) else base)
        parent = classes.get(name.rpartition(".")[2])
        if parent is not None and parent.name not in seen:
            yield parent


def _required_fields(
    cls: ast.ClassDef, classes: Mapping[str, ast.ClassDef], seen: frozenset[str]
) -> bool:
    """Whether a dataclass, or a dataclass it derives from, has a field
    without a default."""
    return any(_required_field(item) for item in cls.body) or any(
        _required_fields(parent, classes, seen | {parent.name})
        for parent in _project_bases(cls, classes, seen)
        if _is_dataclass(parent)
    )


def _abstract_left(
    cls: ast.ClassDef, classes: Mapping[str, ast.ClassDef], seen: frozenset[str]
) -> set[str]:
    """The abstract methods ``cls`` declares or inherits from project classes
    and does not implement: with one left, it cannot be built."""
    own = {
        item.name: any(
            ast.unparse(d) in ABSTRACT_DECORATORS for d in item.decorator_list
        )
        for item in cls.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    inherited: set[str] = set()
    for parent in _project_bases(cls, classes, seen):
        inherited |= _abstract_left(parent, classes, seen | {parent.name})
    return {name for name, abstract in own.items() if abstract} | (inherited - set(own))


def _within(name: str, modules: Sequence[str]) -> bool:
    return any(name == m or name.startswith(f"{m}.") for m in modules)


def _class_reference(
    importer: _Module, target: _Module, name: str, flat: bool = False
) -> tuple[str, Optional[str], Optional[ast.stmt]]:
    """How code of ``importer`` names class ``name`` of ``target``: the
    expression, and the import it needs with the statement to put it after.
    A name the module has already (the class itself, or ``target`` imported
    as a module) needs none; else the import follows the module's own import
    from ``target`` (``from .x import A`` gives ``from .x import B``), or is
    relative; in a ``flat`` project (no package at its root: its modules are
    imported by their own names) absolute."""
    if importer is target:
        return name, None, None
    follow: Optional[ast.ImportFrom] = None
    for node in importer.tree.body:
        if isinstance(node, ast.ImportFrom):
            base = (
                _resolve_relative_module(
                    importer_module=importer.name,
                    filepath_rel=importer.file,
                    level=node.level,
                    module=node.module,
                )
                if node.level
                else node.module or ""
            )
            for alias in node.names:
                full = f"{base}.{alias.name}" if base else alias.name
                if base == target.name and alias.name == name:
                    return alias.asname or name, None, None
                if full == target.name:
                    return f"{alias.asname or alias.name}.{name}", None, None
            if base == target.name and follow is None:
                follow = node
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == target.name and (
                    alias.asname or "." not in alias.name
                ):
                    return f"{alias.asname or alias.name}.{name}", None, None
    if follow is not None:
        spec = "." * follow.level + (follow.module or "")
        return name, f"from {spec} import {name}", follow
    if flat:
        return name, f"from {target.name} import {name}", None
    depth = len(importer.name.split(".")) if importer.name else 0
    if not importer.is_package:
        depth -= 1
    return name, f"from {'.' * (depth + 1)}{target.name} import {name}", None


def _hardcode_collaborator(
    modules: list[_Module],
    instantiable: Optional[Sequence[str]],
    spied: Optional[Spied] = None,
) -> Iterator[_Change]:
    """A constructor builds a collaborator of its own instead of keeping the
    one it was given: ``self.x = x`` (or ``self.x: T = x``) becomes ``self.x
    = C()``, where ``C`` is the first class by name of the ``instantiable``
    modules or classes (every project module by default) that can be built
    without arguments and is no abstract class, nor leaves an inherited
    abstract method unimplemented; never the constructor's own class.
    Without one, nothing. With ``spied`` (``Spied``) only the parameters a
    task gives a spy are hardcoded."""
    classes: dict[str, ast.ClassDef] = {}
    for module in modules:
        for cls in _classes(module):
            classes.setdefault(cls.name, cls)
    buildable = sorted(
        (cls.name, module.name, module)
        for module in modules
        for cls in _classes(module)
        if (
            instantiable is None
            or _within(f"{module.name}.{cls.name}".lstrip("."), instantiable)
        )
        and not _abstract(cls)
        and not _abstract_left(cls, classes, frozenset({cls.name}))
        and _needs_arguments(cls, classes, frozenset({cls.name})) is False
    )
    flat = not any(module.name == "" for module in modules)
    for module in modules:
        for name, method in _methods(module.tree):
            if method.name != "__init__":
                continue
            owner = name.split(".")[0]
            chosen = next(
                (
                    (cls_name, target)
                    for cls_name, _, target in buildable
                    if not (target is module and cls_name == owner)
                ),
                None,
            )
            if chosen is None:
                continue
            cls_name, target = chosen
            allowed = None if spied is None else spied.get((module.file, owner), ())
            for node, _, value in _kept_parameters(method):
                param = value.id
                if allowed is not None and param not in allowed:
                    continue
                reference, line, after = _class_reference(
                    module, target, cls_name, flat
                )
                source = _replace_span(module.text, value, f"{reference}()")
                shift = 0
                if line is not None:
                    at = (
                        int(after.end_lineno or after.lineno)
                        if after is not None
                        else _header_end(module.tree)
                    )
                    source = _insert(source, at, line)
                    shift = 1 if at < node.lineno else 0
                yield _Change(
                    module.file,
                    f"{module.name}: {name} builds its own {param} as "
                    f"{cls_name}() (line {node.lineno + shift})",
                    source,
                    owner=owner,
                    collaborator=param,
                    member=cls_name,
                    line=node.lineno + shift,
                    function=name,
                )


_SCOPES = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda)


def _outside_scopes(node: ast.AST) -> Iterator[ast.AST]:
    """``ast.walk`` that does not enter comprehensions and lambdas: their
    variables do not exist after the statement."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(
            child
            for child in ast.iter_child_nodes(current)
            if not isinstance(child, _SCOPES)
        )


def generate_mutants(
    root: Path,
    operators: Optional[Iterable[str]] = None,
    *,
    libraries: Sequence[str] = DEFAULT_LIBRARIES,
    limit: Optional[int] = None,
    parameter_classes: Optional[ParameterClasses] = None,
    instantiable: Optional[Sequence[str]] = None,
    spied: Optional[Spied] = None,
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
    """
    chosen = list(OPERATORS if operators is None else operators)
    unknown = sorted(set(chosen) - set(OPERATORS))
    if unknown:
        raise ValueError(
            f"unknown operator(s) {', '.join(unknown)}; use {', '.join(OPERATORS)}"
        )
    modules = _modules(root)
    produced: list[Mutant] = []
    for operator in OPERATORS:
        if operator not in chosen:
            continue
        if operator == "add_import":
            found = _add_import(modules, lazy=False)
        elif operator == "lazy_import":
            found = _add_import(modules, lazy=True)
        elif operator == "add_library":
            found = _add_library(modules, libraries)
        elif operator == "dynamic_import":
            found = _dynamic_import(modules, libraries)
        elif operator == "rebuild_injected":
            found = _rebuild_injected(modules)
        elif operator == "drop_call":
            found = _drop_call(modules)
        elif operator == "use_private_name":
            found = _use_private_name(modules)
        elif operator == "break_port":
            found = _break_port(modules)
        elif operator == "foreign_write":
            found = _foreign_write(modules, parameter_classes)
        elif operator == "add_io_call":
            found = _add_io_call(modules)
        elif operator == "mutate_private_container":
            found = _mutate_container(modules, True, parameter_classes)
        elif operator == "mutate_public_container":
            found = _mutate_container(modules, False, parameter_classes)
        elif operator == "stub_role_call":
            found = _stub_role_call(modules)
        elif operator == "add_io_via_helper":
            found = _add_io_via_helper(modules)
        elif operator == "read_private_attribute":
            found = _read_private_attribute(modules, parameter_classes)
        elif operator == "add_builtin_call":
            found = _add_io_call(modules, BUILTIN_CALLS)
        elif operator == "drop_base":
            found = _drop_base(modules)
        elif operator == "concretize_base":
            found = _concretize_base(modules)
        else:
            found = _hardcode_collaborator(modules, instantiable, spied)
        for change in found:
            try:
                for text in (change.source, *(text for _, text in change.also)):
                    ast.parse(text)
            except SyntaxError:
                continue  # an operator never hands out code that does not parse
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
    return produced[:limit] if limit is not None else produced


__all__ = [
    "BUILTIN_CALLS",
    "DEFAULT_LIBRARIES",
    "IO_CALLS",
    "OPERATORS",
    "Mutant",
    "generate_mutants",
]
