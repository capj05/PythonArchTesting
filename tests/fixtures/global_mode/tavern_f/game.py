from abc import ABC, abstractmethod


class Item(ABC):
    def __init__(self, name):
        self.name = name

    def label(self):
        return self.name.upper()

    @abstractmethod
    def use(self, player): ...


class Key(Item):
    def use(self, player):
        return "You turn the " + self.name + "."


class Potion(Item):
    def use(self, player):
        player.heal(10)
        return "You feel better."


class Player:
    def __init__(self):
        self.health = 50
        self._items = []

    def heal(self, amount):
        self.health += amount

    def add(self, item):
        self._items.append(item)

    def find(self, name):
        for item in self._items:
            if item.name == name:
                return item
        return None


class Game:
    def __init__(self):
        self.player = Player()
        self.player.add(Key("key"))
        self.player.add(Potion("potion"))
        self.commands = {"use": self.use, "health": self.health}

    def use(self, arg):
        item = self.player.find(arg)
        if item is None:
            return "You have no such item."
        return item.use(self.player)

    def health(self, arg):
        return "Health: " + str(self.player.health)

    def execute(self, line):
        verb, _, arg = line.partition(" ")
        command = self.commands.get(verb)
        if command is None:
            return "Unknown command."
        return command(arg)

    def ask(self):
        return input("> ")

    def run(self):
        while True:
            try:
                line = self.ask()
            except EOFError:
                break
            if line == "quit":
                break
            print(self.execute(line))


if __name__ == "__main__":
    Game().run()
