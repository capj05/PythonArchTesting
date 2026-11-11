from game import look, new_world, take


def ask():
    return input("> ").strip()


def show(text):
    print("*", text)


def main():
    world = new_world()
    while True:
        try:
            line = ask()
        except EOFError:
            return
        if line == "look":
            show(look(world))
        elif line.startswith("take "):
            show(take(world, line[5:]))
        else:
            show("Unknown command.")


if __name__ == "__main__":
    main()
