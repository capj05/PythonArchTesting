from __future__ import annotations

from .grades import format_summary, parse_grades


def main() -> None:
    text = input("Zadej známky oddělené mezerou: ")
    try:
        grades = parse_grades(text)
    except ValueError as error:
        print(f"Chyba: {error}")
        return
    print(format_summary(grades))
