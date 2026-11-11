class Pocket:
    def __init__(self):
        self.clues = {}

    def add(self, clue):
        if clue in self.clues:
            return False
        self.clues[clue] = len(self.clues) + 1
        return True

    def count(self):
        return len(self.clues)


class State:
    def __init__(self):
        self.pocket = Pocket()
        self.place = "office"

    def go_to(self, place):
        self.place = place
