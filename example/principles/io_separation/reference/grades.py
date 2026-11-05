"""Logic of the grade summary: computes and returns, never talks to the user.

Every function here takes its data as parameters and returns its result. None
of them reads the keyboard, prints, or opens a file -- that is the job of
``app.main``. The markers check exactly that while the functions run; what
they compute is never compared.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import forbid_runtime_calls

# The rules forbid console and file I/O: print(), input() and open() (io.open).
# Declarations are read as literals, so the module names are spelled out.


def parse_grades(text: str) -> list[int]:
    __archtest__: Annotated[  # noqa: F842
        None,
        forbid_runtime_calls(
            "builtins.print",
            "builtins.input",
            "io",
            transitive=True,
            cases=[{"args": ["1 2 3 1"]}, {"args": ["1 x 7"]}],
        ),
    ]
    grades = []
    for word in text.split():
        if not word.isdigit() or not 1 <= int(word) <= 5:
            raise ValueError(f"neplatná známka: {word}")
        grades.append(int(word))
    return grades


def average(grades: list[int]) -> float:
    __archtest__: Annotated[  # noqa: F842
        None,
        forbid_runtime_calls(
            "builtins.print",
            "builtins.input",
            "io",
            transitive=True,
            cases=[{"args": [[1, 2, 3, 1]]}, {"args": [[]]}],
        ),
    ]
    if not grades:
        raise ValueError("žádné známky")
    return sum(grades) / len(grades)


def format_summary(grades: list[int]) -> str:
    __archtest__: Annotated[  # noqa: F842
        None,
        forbid_runtime_calls(
            "builtins.print",
            "builtins.input",
            "io",
            transitive=True,
            cases=[{"args": [[1, 2, 3, 1]]}],
        ),
    ]
    return (
        f"Počet známek: {len(grades)}, průměr: {average(grades):.2f}, "
        f"nejlepší: {min(grades)}, nejhorší: {max(grades)}"
    )
