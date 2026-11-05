"""User interface of the grade summary: the only place with input() and print()."""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import require_runtime_calls

from .grades import format_summary, parse_grades

# The rule requires main to call the logic in grades directly. The cases type
# a valid line and an invalid one on the keyboard (stdin).


def main() -> None:
    __archtest__: Annotated[  # noqa: F842
        None,
        require_runtime_calls(
            "grades",
            cases=[{"args": [], "stdin": "1 2 3 1\n"}, {"args": [], "stdin": "1 x\n"}],
        ),
    ]
    text = input("Zadej známky oddělené mezerou: ")
    try:
        grades = parse_grades(text)
    except ValueError as error:
        print(f"Chyba: {error}")
        return
    print(format_summary(grades))
