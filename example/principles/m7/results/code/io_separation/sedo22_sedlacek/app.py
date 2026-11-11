from .grades import format_summary, parse_grades


def main() -> None:
    text = input("Zadej známky: ")
    try:
        grades = parse_grades(text)
    except ValueError as e:
        print("Chyba: " + str(e))
        return
    print(format_summary(grades))


if __name__ == "__main__":
    main()
