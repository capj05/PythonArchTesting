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
  or is renamed, so the class no longer satisfies a port it implements.

A mutant is a whole new text of one file; nothing is written here.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional, Sequence

from pythonarchtesting.execution.import_edges import (
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
)
DEFAULT_LIBRARIES = ("pickle",)


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


def _rebuild_injected(modules: list[_Module]) -> Iterator[_Change]:
    for module in modules:
        for name, method in _methods(module.tree):
            if method.name != "__init__":
                continue
            self_name = _self_name(method)
            params = {
                arg.arg
                for arg in method.args.posonlyargs
                + method.args.args
                + method.args.kwonlyargs
            } - {self_name}
            for node in ast.walk(method):
                if not (
                    isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Attribute)
                    and isinstance(node.targets[0].value, ast.Name)
                    and node.targets[0].value.id == self_name
                    and isinstance(node.value, ast.Name)
                    and node.value.id in params
                    and node.value.lineno == node.value.end_lineno
                ):
                    continue
                param = node.value.id
                source = _replace_span(module.text, node.value, f"type({param})()")
                yield _Change(
                    module.file,
                    f"{module.name}: {name} builds its own {param} (line {node.lineno})",
                    source,
                    owner=name.split(".")[0],
                    collaborator=param,
                    line=node.lineno,
                )


def _collaborator(call: ast.Call, self_name: Optional[str]) -> Optional[str]:
    """``self.x.m`` when ``call`` is ``self.x.m(...)``."""
    func = call.func
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Attribute)
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == self_name
    ):
        return f"{self_name}.{func.value.attr}.{func.attr}"
    return None


def _collaborator_call(node: ast.stmt, self_name: Optional[str]) -> Optional[str]:
    """``self.x.m`` when ``node`` is the statement ``self.x.m(...)``."""
    if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
        return None
    return _collaborator(node.value, self_name)


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
    """``(class, attribute) -> constructor parameter`` for ``self.a = p``."""
    found: dict[tuple[str, str], str] = {}
    for name, method in _methods(module.tree):
        if method.name != "__init__":
            continue
        self_name = _self_name(method)
        for node in ast.walk(method):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Attribute)
                and isinstance(node.targets[0].value, ast.Name)
                and node.targets[0].value.id == self_name
                and isinstance(node.value, ast.Name)
            ):
                found[(name.split(".")[0], node.targets[0].attr)] = node.value.id
    return found


def _drop_call(modules: list[_Module]) -> Iterator[_Change]:
    for module in modules:
        injected = _injected(module)
        for name, method in _methods(module.tree):
            self_name = _self_name(method)
            owner = name.split(".")[0]

            def about(call: ast.Call) -> dict[str, Any]:
                func = call.func
                assert isinstance(
                    func, ast.Attribute
                )  # nosec B101 - a collaborator call
                assert isinstance(func.value, ast.Attribute)  # nosec B101
                attribute = func.value.attr
                return {
                    "owner": owner,
                    "collaborator": injected.get(
                        (owner, attribute), attribute.lstrip("_")
                    ),
                    "member": func.attr,
                    "line": call.lineno,
                }

            found: list[tuple[int, int, _Change]] = []
            statements: set[int] = set()
            for node in ast.walk(method):
                if not isinstance(node, ast.stmt):
                    continue
                call = _collaborator_call(node, self_name)
                if call is None:
                    continue
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
                            **about(node.value),  # type: ignore[attr-defined]
                        ),
                    )
                )
            # A call whose result is used (``x = self.d.apply(x)``): the
            # collaborator is bypassed, its argument taken as the result.
            for node in ast.walk(method):
                if not isinstance(node, ast.Call) or id(node) in statements:
                    continue
                call = _collaborator(node, self_name)
                if call is None or node.lineno != node.end_lineno:
                    continue
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
                            **about(node),
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


def generate_mutants(
    root: Path,
    operators: Optional[Iterable[str]] = None,
    *,
    libraries: Sequence[str] = DEFAULT_LIBRARIES,
    limit: Optional[int] = None,
) -> list[Mutant]:
    """Every mutant the ``operators`` (all by default) make of the project at ``root``.

    The order is stable: by operator, then by file and position. ``limit``
    keeps the first that many.
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
        else:
            found = _break_port(modules)
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
                )
            )
    return produced[:limit] if limit is not None else produced


__all__ = ["DEFAULT_LIBRARIES", "OPERATORS", "Mutant", "generate_mutants"]
