from .grades import format_summary, parse_grades


def main() -> None:
    line = input("Zadej známky: ")
    try:
        grades = parse_grades(line)
    except ValueError as error:
        print("Chyba: " + str(error))
        return
    print(format_summary(grades))
