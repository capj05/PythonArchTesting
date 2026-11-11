def moor(harbor, boat):
    if boat in harbor["boats"]:
        harbor["boats"].remove(boat)
        harbor["moored"].append(boat)
        return "Moored the " + boat + "."
    return "No such boat."


def list_boats(harbor):
    return "Boats: " + ", ".join(harbor["boats"])
