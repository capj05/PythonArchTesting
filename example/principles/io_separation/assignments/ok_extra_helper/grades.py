"""Grade summary logic with a validation helper."""


def is_valid_grade(word):
    return word.isdigit() and 1 <= int(word) <= 5


def parse_grades(text):
    words = text.split()
    bad = [w for w in words if not is_valid_grade(w)]
    if bad:
        raise ValueError(f"neplatné známky: {', '.join(bad)}")
    return [int(w) for w in words]


def average(grades):
    if not grades:
        raise ValueError("žádné známky")
    return sum(grades) / len(grades)


def format_summary(grades):
    return (
        f"Počet známek: {len(grades)}, průměr: {average(grades):.2f}, "
        f"nejlepší: {min(grades)}, nejhorší: {max(grades)}"
    )
