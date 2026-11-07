def parse_grades(text: str) -> list[int]:
    parts = text.split()
    if len(parts) == 0:
        raise ValueError("nebyla zadána žádná známka.")
    result = []
    for p in parts:
        try:
            n = int(p)
        except ValueError:
            raise ValueError('"' + p + '" není celé číslo.')
        result.append(n)
    for n in result:
        if n < 1 or n > 5:
            raise ValueError("známka " + str(n) + " je mimo rozsah 1 až 5.")
    return result


def average(grades: list[int]) -> float:
    return sum(grades) / len(grades)


def format_summary(grades: list[int]) -> str:
    return "Počet známek: " + str(len(grades)) + ", průměr: " + format(average(grades), ".2f")
