"""The project the operators mutate: its modules as read from disk, what
an operator makes of them (``Change``), the mutant ``generate_mutants``
hands out of it (``Mutant``) and what a task says about them.
"""

from __future__ import annotations

import ast
import io
import os
import re
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, Mapping, Optional

from pythonarchtesting.constants import FileConstants

# What the cases of a task say about the parameters of a function:
# ``(file, function) -> {parameter: class name}`` for each parameter a case
# builds a project object for (``$new``). A function listed here gets no
# other parameter's class guessed: its cases show what it is called with.
ParameterClasses = Mapping[tuple[str, str], Mapping[str, str]]


# The constructor parameters a task gives a spy (``{"$spy": ...}`` in its
# ``[init]``): ``(file, class) -> parameter names``.
Spied = Mapping[tuple[str, str], Collection[str]]


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
class Change:
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
class Module:
    name: str  # dotted, "" for the root package
    file: str  # relative, with "/"
    text: str
    tree: ast.Module
    is_package: bool


# A coding line (PEP 263), in one of the first two lines of a file.
_CODING = re.compile(r"^([ \t\f]*#.*?coding[:=][ \t]*)([-\w.]+)", re.MULTILINE)


def _source_text(data: bytes) -> str:
    """The text of a Python file as Python reads it: UTF-8 (a BOM dropped)
    or the encoding its coding line names. A mutant is written as UTF-8, so
    a coding line naming another encoding says ``utf-8`` in the text.
    Raises ``SyntaxError`` when the bytes do not decode."""
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
        text = data.decode(encoding)
    except (SyntaxError, LookupError, UnicodeDecodeError) as error:
        raise SyntaxError(
            f"does not decode as UTF-8 or the encoding its coding line names "
            f"({error})"
        ) from error
    if encoding not in ("utf-8", "utf-8-sig"):
        head, newline, rest = text.partition("\n")
        second, newline2, rest = rest.partition("\n")
        lines = _CODING.sub(r"\1utf-8", head + newline + second, count=1)
        text = lines + newline2 + rest
    return text


def _skipped_directory(part: str) -> bool:
    """A directory no project module is in: a hidden one, ``__pycache__`` or
    a virtual environment (``FileConstants.EXCLUDED_DIRS``, as the static
    discovery skips)."""
    return part.startswith(".") or part in FileConstants.EXCLUDED_DIRS


def _python_files(root: Path) -> list[Path]:
    """The ``.py`` files under ``root``, sorted, none in a skipped directory
    (``_skipped_directory``) nor hidden."""
    found: list[Path] = []
    for directory, subdirectories, files in os.walk(root):
        subdirectories[:] = [d for d in subdirectories if not _skipped_directory(d)]
        found += [
            Path(directory) / name
            for name in files
            if name.endswith(".py") and not name.startswith(".")
        ]
    return sorted(found)


def load_modules(
    root: Path, skipped: Optional[list[tuple[str, str]]] = None
) -> list[Module]:
    """The project's modules under ``root``. A file that does not decode or
    parse is none; with ``skipped``, it is listed there as ``(file, why)``."""
    modules = []
    for path in _python_files(root):
        relative = path.relative_to(root)
        parts = list(relative.with_suffix("").parts)
        is_package = parts[-1] == "__init__"
        if is_package:
            parts = parts[:-1]
        try:
            text = _source_text(path.read_bytes())
            tree = ast.parse(text)
        except (SyntaxError, ValueError, OSError) as error:
            if skipped is not None:
                skipped.append((relative.as_posix(), str(error)))
            continue
        modules.append(
            Module(".".join(parts), relative.as_posix(), text, tree, is_package)
        )
    return modules
