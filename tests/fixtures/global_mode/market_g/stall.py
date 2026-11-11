from goods import buy, prices


def run():
    stock = {"apple": 3, "bread": 5}
    basket = []
    while True:
        command = input("market> ")
        if command == "buy":
            print(buy(stock, basket))
        elif command == "prices":
            print(prices(stock))
        elif command == "leave":
            break


if __name__ == "__main__":
    run()
