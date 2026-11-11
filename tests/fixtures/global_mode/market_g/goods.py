def buy(stock, basket):
    name = input("Buy what? ")
    if name in stock:
        basket.append(name)
        return "Bought " + name + "."
    return "No " + name + " today."


def prices(stock):
    return ", ".join(name + " " + str(price) for name, price in sorted(stock.items()))
