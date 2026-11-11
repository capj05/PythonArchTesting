class Lot:
    def __init__(self):
        self.broken = ["van"]
        self.fixed = []

    def summary(self):
        return "Broken: " + ", ".join(self.broken)

    def fix(self, car):
        if car in self.broken:
            self.broken.remove(car)
            self.fixed.append(car)
            print("Fixed the " + car + ".")
        else:
            print("The " + car + " is fine.")
