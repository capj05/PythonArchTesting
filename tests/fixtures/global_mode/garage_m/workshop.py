from cars import Lot
from panel import Panel


class Workshop:
    def __init__(self):
        self.lot = Lot()
        self.panel = Panel()

    def run(self):
        while True:
            command = self.panel.read()
            if command == "lot":
                self.panel.show(self.lot.summary())
            elif command.startswith("fix "):
                self.lot.fix(command[4:])
            elif command == "done":
                break


if __name__ == "__main__":
    Workshop().run()
