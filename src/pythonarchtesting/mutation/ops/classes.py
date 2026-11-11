"""Operators that change a class's interface or bases: ``break_port``,
``drop_base`` and ``concretize_base``.
"""

from __future__ import annotations

import ast
from typing import Iterator

from pythonarchtesting.mutation.class_model import top_classes
from pythonarchtesting.mutation.functions import class_methods
from pythonarchtesting.mutation.project import Change, Module
from pythonarchtesting.mutation.source_edit import alone, with_bases
from pythonarchtesting.util.ast_utils import (
    ABSTRACT_DECORATORS,
    ABSTRACT_METACLASSES,
    abstract_base,
)


def _public_methods(
    tree: ast.Module, text: str
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Public methods of top-level classes whose body starts on its own line."""
    for name, method in class_methods(tree):
        if method.name.startswith("_"):
            continue
        if method.body[0].lineno <= method.lineno or not alone(text, method.body[0]):
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


def break_port(modules: list[Module]) -> Iterator[Change]:
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
            yield Change(
                module.file,
                f"{module.name}: {name} takes a new required parameter",
                "".join(lines[:first] + [_header(changed, indent)] + lines[body:]),
            )
            renamed = copy.copy(method)
            renamed.name = f"{method.name}_renamed"
            yield Change(
                module.file,
                f"{module.name}: {name} is renamed",
                "".join(lines[:first] + [_header(renamed, indent)] + lines[body:]),
            )


def drop_base(modules: list[Module]) -> Iterator[Change]:
    """A top-level class no longer names one of its bases, ``object``
    excepted: one mutant per class and base; keywords stay."""
    for module in modules:
        for cls in top_classes(module):
            for base in cls.bases:
                name = ast.unparse(base)
                if name == "object":
                    continue
                kept: list[ast.AST] = [b for b in cls.bases if b is not base]
                source = with_bases(module.text, cls, kept + list(cls.keywords))
                if source is None:
                    continue
                yield Change(
                    module.file,
                    f"{module.name}: {cls.name} no longer derives from {name} "
                    f"(line {cls.lineno})",
                    source,
                    owner=cls.name,
                    member=name,
                    line=cls.lineno,
                    function=cls.name,
                )


def concretize_base(modules: list[Module]) -> Iterator[Change]:
    """An abstract top-level class becomes an ordinary one: ``ABC`` and
    ``Protocol`` leave its bases, ``metaclass=ABCMeta`` its keywords and
    ``@abstractmethod`` (on lines of its own) its methods. The imports stay.
    A class with none of these gives no mutant."""
    for module in modules:
        for cls in top_classes(module):
            bases = [b for b in cls.bases if not abstract_base(b)]
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
                rewritten = with_bases(source, cls, [*bases, *keywords])
                if rewritten is None:
                    continue
                source = rewritten
            removed += ["@" + ast.unparse(d) for d in decorators]
            yield Change(
                module.file,
                f"{module.name}: {cls.name} is no longer abstract, without "
                f"{', '.join(dict.fromkeys(removed))} (line {cls.lineno})",
                source,
                owner=cls.name,
                line=cls.lineno,
                function=cls.name,
            )
