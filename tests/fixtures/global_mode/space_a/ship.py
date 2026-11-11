from abc import ABC, abstractmethod


class Cargo:
    def __init__(self, capacity=3):
        self._crates = []
        self.capacity = capacity

    def load(self, crate):
        if len(self._crates) >= self.capacity:
            return False
        self._crates.append(crate)
        return True

    def count(self):
        return len(self._crates)


class Module(ABC):
    @abstractmethod
    def power(self):
        """Energy the module produces per turn."""


class Reactor(Module):
    def power(self):
        return 10


class SolarPanel(Module):
    def power(self):
        return 3


class State:
    def __init__(self):
        self.cargo = Cargo()
        self.modules = [Reactor(), SolarPanel()]
        self.room = "bridge"

    def go_to(self, room):
        self.room = room
