def forge(bars, metal):
    if metal in bars:
        bars.remove(metal)
        return "A " + metal + " blade."
    return "No " + metal + " left."


def rack(bars):
    return sorted(bars)
