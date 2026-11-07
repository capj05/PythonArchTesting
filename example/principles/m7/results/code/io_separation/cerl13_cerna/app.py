from .grades import format_summary, parse_grades


def main() -> None:
    text = input("Zadej známky: ")
    try:
        grades = parse_grades(text)
    except ValueError as error:
        print("Chyba: " + str(error))
        return
    print(format_summary(grades))
