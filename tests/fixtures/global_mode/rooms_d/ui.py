from game import look, new_world, take


def main():
    world = new_world()
    while True:
        try:
            line = input("> ")
        except EOFError:
            return
        if line == "look":
            print(look(world))
        elif line.startswith("take "):
            print(take(world, line[5:]))
        else:
            print("Unknown command.")


if __name__ == "__main__":
    main()
