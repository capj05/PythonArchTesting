def search(state, words):
    clue = words[1] if len(words) > 1 else "fingerprint"
    if state.pocket.add(clue):
        return "You found a " + clue + "."
    return "You already have the " + clue + "."


def walk(state, words):
    state.go_to(words[1] if len(words) > 1 else state.place)
    return "You walk to the " + state.place + "."


def notes(state, words):
    return "Clues in pocket: " + str(state.pocket.count())
