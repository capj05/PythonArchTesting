from .grades import format_summary, parse_grades


def main() -> None:
    text = input("Zadej známky: ")
    try:
        grades = parse_grades(text)
        print(format_summary(grades))
    except ValueError as e:
        print("Chyba: " + str(e))
