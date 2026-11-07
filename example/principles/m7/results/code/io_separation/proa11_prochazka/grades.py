def parse_grades(text: str) -> list[int]:
    items = text.split()
    if len(items) == 0:
        raise ValueError("nebyla zadána žádná známka.")

    grades = []
    for item in items:
        try:
            grade = int(item)
        except ValueError:
            raise ValueError('"' + item + '" není celé číslo.')
        if grade < 1 or grade > 5:
            raise ValueError("známka " + str(grade) + " je mimo rozsah 1 až 5.")
        grades.append(grade)

    return grades


def average(grades: list[int]) -> float:
    total = 0
    for grade in grades:
        total = total + grade
    return total / len(grades)


def format_summary(grades: list[int]) -> str:
    avg = average(grades)
    return f"Počet známek: {len(grades)}, průměr: {avg:.2f}"
