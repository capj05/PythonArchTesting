import actions

COMMANDS = {"go": actions.go, "take": actions.take}


def parse(line):
    verb, _, arg = line.strip().partition(" ")
    return verb, arg


def play(state):
    while True:
        line = input("> ")
        if line == "quit":
            break
        verb, arg = parse(line)
        action = COMMANDS.get(verb)
        if action is None:
            print("Unknown command.")
        else:
            print(action(state, arg))
