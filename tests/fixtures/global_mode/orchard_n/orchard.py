trees = {"apple": 3, "pear": 1}
crate = []


def count():
    return ", ".join(name + " " + str(left) for name, left in sorted(trees.items()))


def pick(fruit):
    if trees.get(fruit, 0) > 0:
        trees[fruit] -= 1
        crate.append(fruit)
        print("Picked a " + fruit + ".")
    else:
        print("No " + fruit + " left.")


def main():
    while True:
        word = input("orchard> ")
        if word == "count":
            print(count())
        elif word.startswith("pick "):
            pick(word[5:])
        elif word == "home":
            break


if __name__ == "__main__":
    main()
