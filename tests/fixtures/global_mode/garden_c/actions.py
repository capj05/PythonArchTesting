EXITS = {"hall": {"north": "lab"}, "lab": {"south": "hall"}}


def go(state, direction):
    target = EXITS[state["room"]].get(direction)
    if target is None:
        return "You cannot go there."
    state["room"] = target
    return "You are in the " + target + "."


def take(state, item):
    state["items"].append(item)
    return "Taken: " + item


def new_state():
    return {"room": "hall", "items": []}
