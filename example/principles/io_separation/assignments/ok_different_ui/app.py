from .grades import average, format_summary, parse_grades


def main():
    while True:
        text = input("Známky (1-5): ")
        try:
            grades = parse_grades(text)
            break
        except ValueError as error:
            print("Zkus to znovu:", error)
    print("=== Výsledek ===")
    print(format_summary(grades))
    if average(grades) < 1.5:
        print("Výborně!")
