def take(state, words):
    crate = words[1] if len(words) > 1 else "box"
    state.cargo._crates.append(crate)
    return "You take the " + crate + "."


def load(state, words):
    crate = words[1] if len(words) > 1 else "box"
    if state.cargo.load(crate):
        return "Loaded " + crate + "."
    return "The hold is full."


def total_power(modules):
    return sum(m.power() for m in modules)


def status(state, words):
    print("Room:", state.room)
    print("Crates:", state.cargo.count())
    print("Power:", total_power(state.modules))
    return ""


def go(state, words):
    state.go_to(words[1] if len(words) > 1 else state.room)
    return "You are in the " + state.room + "."
