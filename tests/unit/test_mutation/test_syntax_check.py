"""The parse check of mutants: only the touched statements, the whole text's answer."""

from __future__ import annotations

import ast
import random
from pathlib import Path

import pytest

from pythonarchtesting.mutation import operators
from pythonarchtesting.mutation.operators import OPERATORS, generate_mutants

_TEXT = '''"""A module."""

from __future__ import annotations

import os


@staticmethod
def helper(x):
    if x:
        return 1
    else:
        return 2


class Shop:
    def __init__(self):
        self._stock = {}

    def remove(self, k):
        return self._stock.pop(k, None)


x = 1; y = 2
z = (
    3
)
'''

_EXAMPLES = Path(__file__).resolve().parents[3] / "example" / "principles"


def _module(text: str) -> operators._Module:
    return operators._Module("m", "m.py", text, ast.parse(text), False)


def _whole(text: str) -> bool:
    try:
        ast.parse(text)
    except SyntaxError:
        return False
    return True


@pytest.mark.parametrize(
    "new",
    [
        _TEXT,
        _TEXT.replace("        return 2\n", "        return 2\n    print(1)\n"),
        # An ``else`` at the left margin after a statement: no statement.
        _TEXT.replace("class Shop:", "else:\n    pass\nclass Shop:"),
        # A line glued to the statement after the change.
        _TEXT.replace("        return 2\n\n\n", "        return 2"),
        # A bracket opened in the change and closed in the kept rest.
        _TEXT.replace("x = 1; y = 2\nz = (\n", "x = 1; y = (2\nz = (\n"),
        _TEXT.replace("    3\n)\n", "    3\n"),
        _TEXT.replace(
            "import os\n", "import os\nfrom __future__ import barry_as_FLUFL\n"
        )
        + "w = 1 != 2\n",
        _TEXT.replace("import os\n", "import os(\n"),
        _TEXT.replace("class Shop:\n", "class Shop:\n  "),
        _TEXT.replace("\n", "\r"),
        "",
    ],
)
def test_the_answer_is_the_whole_texts(new: str) -> None:
    assert operators._Syntax(_module(_TEXT)).parses(new) is _whole(new)


def test_random_edits_get_the_whole_texts_answer() -> None:
    pieces = ["(", ")", "else:\n", "    pass\n", "if x:\n", '"""', "\\\n", "@d\n", "\r"]
    pieces += ["  y\n", "from __future__ import barry_as_FLUFL\n", "a <> b\n", "\t"]
    paths = sorted(_EXAMPLES.glob("*/reference/**/*.py"))
    assert paths
    chance = random.Random(7)
    for path in paths:
        text = path.read_text(encoding="utf-8")
        check = operators._Syntax(_module(text))
        lines = text.splitlines(keepends=True)
        for _ in range(60):
            changed = list(lines)
            at = chance.randrange(len(changed) + 1)
            if chance.random() < 0.5 or not changed:
                changed.insert(at, chance.choice(pieces))
            else:
                del changed[min(at, len(changed) - 1)]
            new = "".join(changed)
            assert check.parses(new) is _whole(new), (path, new)


def test_a_mutant_is_parsed_by_the_statements_it_touches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = "".join(
        f"def f{i}(inv, x):\n    y = x + {i}\n    return inv.remove(y)\n\n\n"
        for i in range(60)
    )
    (tmp_path / "shop.py").write_text(body, encoding="utf-8")
    parsed: list[int] = []
    original = ast.parse

    def counting(source: str | bytes, *args: object, **kwargs: object) -> ast.AST:
        parsed.append(len(source))
        return original(source, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(operators.ast, "parse", counting)

    mutants = generate_mutants(tmp_path, ["add_io_call"])

    assert len(mutants) >= 60
    # The module is parsed once to read it; each mutant only in its function.
    assert sum(1 for size in parsed if size >= len(body)) == 1


@pytest.mark.parametrize("principle", ["encapsulation", "io_separation"])
def test_a_limit_keeps_the_first_mutants_and_stops_there(
    principle: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference = _EXAMPLES / principle / "reference"
    every = generate_mutants(reference)
    assert len(every) > 3
    for limit in (0, 1, 3, len(every), len(every) + 5):
        assert generate_mutants(reference, limit=limit) == every[:limit]

    def unreachable(*_: object, **__: object) -> object:
        raise AssertionError("an operator ran after the limit was reached")

    first = every[0].operator
    for name in OPERATORS[OPERATORS.index(first) + 1 :]:
        target = f"_{name}"
        if hasattr(operators, target):
            monkeypatch.setattr(operators, target, unreachable)
    monkeypatch.setattr(operators, "_hardcode_collaborator", unreachable)
    assert generate_mutants(reference, limit=1) == every[:1]
