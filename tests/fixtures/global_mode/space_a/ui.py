from space_a.actions import go, load, status, take
from space_a.ship import State

COMMANDS = {"take": take, "load": load, "go": go, "status": status}


def main():
    state = State()
    while True:
        try:
            line = input("> ")
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
    main()
