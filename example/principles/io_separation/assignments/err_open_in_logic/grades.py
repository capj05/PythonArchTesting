"""Grade summary logic."""


def parse_grades(text):
    grades = []
    try:
        with open("dalsi_znamky.txt", encoding="utf-8") as file:
            text = text + " " + file.read()
    except FileNotFoundError:
        pass
    for word in text.split():
        if not word.isdigit() or not 1 <= int(word) <= 5:
            raise ValueError(f"neplatná známka: {word}")
        grades.append(int(word))
    return grades


def average(grades):
    if not grades:
        raise ValueError("žádné známky")
    return sum(grades) / len(grades)


def format_summary(grades):
    return (
        f"Počet známek: {len(grades)}, průměr: {average(grades):.2f}, "
        f"nejlepší: {min(grades)}, nejhorší: {max(grades)}"
    )
