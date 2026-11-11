from __future__ import annotations


def parse_grades(text: str) -> list[int]:
    grades = []
    for word in text.split():
        if not word.isdigit() or not 1 <= int(word) <= 5:
            raise ValueError(f"neplatná známka: {word}")
        grades.append(int(word))
    return grades


def average(grades: list[int]) -> float:
    if not grades:
        raise ValueError("žádné známky")
    return sum(grades) / len(grades)


def format_summary(grades: list[int]) -> str:
    return (
        f"Počet známek: {len(grades)}, průměr: {average(grades):.2f}, "
        f"nejlepší: {min(grades)}, nejhorší: {max(grades)}"
    )
