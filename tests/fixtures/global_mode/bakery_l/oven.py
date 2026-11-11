def listing(shop):
    return "Fresh: " + ", ".join(shop["shelf"])


def sell(shop, pastry):
    shelf = shop["shelf"]
    sold = shop["sold"]
    if pastry in shelf:
        shelf.remove(pastry)
        sold.append(pastry)
        print("Sold a " + pastry + ".")
    else:
        print("No " + pastry + " today.")
