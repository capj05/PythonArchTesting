"""User interface of the grade summary -- computes everything itself."""


def main():
    text = input("Zadej známky oddělené mezerou: ")
    grades = [int(w) for w in text.split()]
    total = 0
    for g in grades:
        total += g
    print(f"Počet známek: {len(grades)}, průměr: {total / len(grades):.2f}, "
          f"nejlepší: {min(grades)}, nejhorší: {max(grades)}")
