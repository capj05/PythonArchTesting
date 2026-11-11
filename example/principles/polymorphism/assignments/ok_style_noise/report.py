def total_area(shapes):
    # součet ploch všech tvarů
    soucet = 0.0
    for tvar in shapes:
        soucet = soucet + tvar.area()

    return soucet


def describe_all(shapes):
    radky = []
    for tvar in shapes:
        radky.append(tvar.describe() + ": plocha " + format(tvar.area(), ".2f"))
    return '\n'.join(radky)
