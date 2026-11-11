from rules import can_take


def new_world():
    return {"room": "hall", "items": ["lamp"], "bag": []}


def look(world):
    return "You are in the " + world["room"] + "."


def take(world, name):
    if can_take(world["items"], name):
        world["items"].remove(name)
        world["bag"].append(name)
        return "Taken."
    return "Nothing here."
