from case import State
from commands import notes, search, walk

COMMANDS = {"search": search, "walk": walk, "notes": notes}


def run():
    state = State()
    while True:
        try:
            line = input("? ")
        except EOFError:
            break
        words = line.split()
        if not words:
            continue
        if words[0] == "konec":
            break
        action = COMMANDS.get(words[0])
        print(action(state, words) if action else "Unknown command.")


if __name__ == "__main__":
    run()
