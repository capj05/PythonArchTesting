class Cabin:
    def __init__(self):
        self.place = "porch"
        self.wood = 2
        self.fire = False
        self.open = True

    def walk(self, place):
        if place in ("porch", "shed", "hearth"):
            self.place = place
            return "You walk to the " + place + "."
        return "You cannot go there."

    def light(self):
        if self.place == "hearth" and self.wood > 0:
            self.wood -= 1
            self.fire = True
            return "The fire crackles."
        return "Nothing to light here."

    def handle(self, line):
        verb, _, rest = line.partition(" ")
        if verb == "walk":
            return self.walk(rest)
        if verb == "light":
            return self.light()
        if verb == "sleep":
            self.open = False
            return "Good night."
        return "Hm?"

    def run(self):
        while self.open:
            print(self.handle(input("cabin> ")))


if __name__ == "__main__":
    Cabin().run()
