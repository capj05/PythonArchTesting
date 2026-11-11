def parse_grades(text: str) -> list[int]:
    parts = text.split()
    if len(parts) == 0:
        raise ValueError("nebyla zadána žádná známka.")

    grades = []
    for part in parts:
        try:
            number = int(part)
        except ValueError:
            raise ValueError('"' + part + '" není celé číslo.')
        if number < 1 or number > 5:
            raise ValueError("známka " + str(number) + " je mimo rozsah 1 až 5.")
        grades.append(number)
    return grades


def average(grades: list[int]) -> float:
    return sum(grades) / len(grades)


def format_summary(grades: list[int]) -> str:
    return "Počet známek: " + str(len(grades)) + ", průměr: " + format(average(grades), ".2f")
