import oven


def main():
    shop = {"shelf": ["bun", "loaf"], "sold": []}
    while True:
        order = input("bakery> ")
        if order == "list":
            print(oven.listing(shop))
        elif order.startswith("sell "):
            oven.sell(shop, order[5:])
        elif order == "close":
            break


if __name__ == "__main__":
    main()
