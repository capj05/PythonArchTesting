def parse_grades(text: str) -> list[int]:
    parts = text.split()
    if len(parts) == 0:
        raise ValueError("nebyla zadána žádná známka.")
    grades = []
    for p in parts:
        try:
            g = int(p)
        except ValueError:
            raise ValueError('"' + p + '" není celé číslo.')
        if g < 1 or g > 5:
            raise ValueError("známka " + str(g) + " je mimo rozsah 1 až 5.")
        grades.append(g)
    return grades


def average(grades: list[int]) -> float:
    return sum(grades) / len(grades)


def format_summary(grades: list[int]) -> str:
    avg = average(grades)
    return "Počet známek: " + str(len(grades)) + ", průměr: " + format(avg, ".2f")
