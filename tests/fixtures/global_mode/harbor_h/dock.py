from orders import ORDERS


def main():
    harbor = {"boats": ["skiff"], "moored": []}
    while True:
        try:
            words = input("dock> ").split()
        except EOFError:
            return
        if not words:
            continue
        order = ORDERS.get(words[0])
        if order is None:
            print("Unknown order.")
        elif words[0] == "moor":
            print(order(harbor, words[1] if len(words) > 1 else ""))
        else:
            print(order(harbor))


if __name__ == "__main__":
    main()
