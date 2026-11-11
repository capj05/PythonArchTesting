from anvil import forge, rack
from banner import announce, list_out


def main():
    bars = ["iron", "bronze"]
    while True:
        order = input("smithy> ")
        if order.startswith("forge "):
            announce(forge(bars, order[6:]))
        elif order == "rack":
            list_out(rack(bars))
        elif order == "close":
            break


if __name__ == "__main__":
    main()
