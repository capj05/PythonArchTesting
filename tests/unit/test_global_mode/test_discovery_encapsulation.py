"""Role discovery for ``encapsulation``: the classes whose state is a
container their methods change, and the code around them, found in the code
alone. The owner only decides whether the principle applies (design § 13
point 4); the clients are every function and foreign method."""

from __future__ import annotations

from pathlib import Path

import pytest

from pythonarchtesting.global_mode.discovery import discover_roles
from pythonarchtesting.global_mode.model import BoundEntity, RoleDiscovery
from pythonarchtesting.global_mode.selftask import _source_entities

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "global_mode"

_STILL = """class Shelf:
    def __init__(self):
        self.books = ["atlas"]
        self.books.append("map")

    def first(self):
        return self.books[0]


class Label:
    def __init__(self, text):
        self.text = text
        self.tags = {}

    def show(self):
        return self.text + str(len(self.tags))

    def rename(self, text):
        self.text = text
"""

_WORLD = """class Bag:
    def __init__(self):
        self._items = set()

    def put(self, item):
        self._items.add(item)

    def has(self, item):
        return item in self._items


class Room:
    def __init__(self, name):
        self.name = name

    def describe(self):
        return "You are in " + self.name

    def _secret(self):
        return "hidden"


def make_bag():
    return Bag()
"""

_GAME = """from world import Bag, Room


def play(bag):
    bag.put("key")


def _helper():
    return Room("hall")
"""

_ONLY_PRIVATE = """def _hidden():
    return 1
"""

_HOUSE = """class House:
    def __init__(self):
        self.rooms = []
        self.setup()

    def setup(self):
        self.doors = dict()

    def open(self, door):
        self.doors[door] = True

    def build(self, room):
        self.rooms.insert(0, room)
"""

_STUBS = '''import abc
from abc import ABC, abstractmethod


class Tool(ABC):
    @abstractmethod
    def use(self):
        return "used"

    @abc.abstractmethod
    def wear(self):
        """How much the tool wears."""

    def name(self):
        raise NotImplementedError("subclass")

    def weight(self):
        """The weight."""
        ...

    def price(self):
        pass

    def label(self):
        return "tool"


class Plain:
    def name(self):
        raise NotImplementedError("subclass")

    def weight(self):
        """The weight."""
        ...

    def price(self):
        pass

    def label(self):
        return "plain"
'''


_ROOMS = """class Item:
    def __init__(self, name):
        self.name = name


class Place:
    def __init__(self, names):
        self.initialize(names)

    def initialize(self, names):
        self.items = [Item(n) for n in names]

    def look(self):
        return len(self.items)


class Shop(Place):
    def add(self, item):
        self.items.append(item)

    def remove(self, item):
        self.items.remove(item)
"""

_SACK = """class Sack:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items += [item]
"""

_OUTSIDE_WORLD = """class Inventory:
    def __init__(self):
        self.items = []

    def show(self):
        return ", ".join(self.items)


class State:
    def __init__(self):
        self.inventory = Inventory()
"""

_OUTSIDE_ACTIONS = """def take(state, item):
    state.inventory.items.append(item)
    return "You take the " + item + "."
"""


def _names(discovery: RoleDiscovery, role: str) -> list[str]:
    return [b.entity for b in discovery.roles[role]]


def test_cargo_is_owner_of_space_a() -> None:
    discovery = discover_roles("encapsulation", _source_entities(FIXTURES / "space_a"))

    assert discovery.roles["owner"] == (
        BoundEntity(
            "ship.Cargo", "code", "creates list _crates in __init__, changed by load()"
        ),
    )
    # ship.Module.power is abstract: no case can build its object.
    assert _names(discovery, "client") == [
        "actions",
        "ship.Reactor.power",
        "ship.SolarPanel.power",
        "ship.State.go_to",
        "ui",
    ]
    assert discovery.conflicts == ()
    assert discovery.not_applied is None


def test_pocket_is_owner_with_public_dict() -> None:
    discovery = discover_roles(
        "encapsulation", _source_entities(FIXTURES / "detective_b")
    )

    assert discovery.roles["owner"] == (
        BoundEntity(
            "case.Pocket", "code", "creates dict clues in __init__, changed by add()"
        ),
    )
    assert _names(discovery, "client") == ["case.State.go_to", "commands", "console"]
    assert discovery.not_applied is None


def test_class_without_mutating_method_is_not_owner(tmp_path: Path) -> None:
    # Shelf changes its list only in __init__; Label has a dict no method
    # changes, and its rename assigns a plain attribute.
    (tmp_path / "still.py").write_text(_STILL, encoding="utf-8")

    discovery = discover_roles("encapsulation", _source_entities(tmp_path))

    assert discovery.roles["owner"] == ()
    assert discovery.not_applied is not None
    assert discovery.not_applied.startswith("owner not found: ")
    # The clients are still listed: the missing owner alone gates the principle.
    assert _names(discovery, "client") == [
        "still.Label.rename",
        "still.Label.show",
        "still.Shelf.first",
    ]


def test_clients_bind_modules_and_foreign_methods(tmp_path: Path) -> None:
    (tmp_path / "world.py").write_text(_WORLD, encoding="utf-8")
    (tmp_path / "game.py").write_text(_GAME, encoding="utf-8")
    (tmp_path / "util.py").write_text(_ONLY_PRIVATE, encoding="utf-8")

    discovery = discover_roles("encapsulation", _source_entities(tmp_path))

    assert _names(discovery, "owner") == ["world.Bag"]
    # A module is bound whole by its path, also the owner's own module; the
    # owner's methods, private methods and a module of private functions
    # are no clients.
    assert discovery.roles["client"] == (
        BoundEntity("game", "code", "module of top-level public functions"),
        BoundEntity("world", "code", "module of top-level public functions"),
        BoundEntity(
            "world.Room.describe", "code", "public method of world.Room, not an owner"
        ),
    )
    assert discovery.conflicts == ()


def test_container_built_in_a_method_init_calls_counts(tmp_path: Path) -> None:
    (tmp_path / "house.py").write_text(_HOUSE, encoding="utf-8")

    discovery = discover_roles("encapsulation", _source_entities(tmp_path))

    assert discovery.roles["owner"] == (
        BoundEntity(
            "house.House",
            "code",
            "creates dict doors in setup(), changed by open(); "
            "creates list rooms in __init__, changed by build()",
        ),
    )


def test_project_without_classes_has_no_owner(tmp_path: Path) -> None:
    (tmp_path / "game.py").write_text(
        "ROOMS = {}\n\n\ndef add(name):\n    ROOMS[name] = []\n", encoding="utf-8"
    )

    discovery = discover_roles("encapsulation", _source_entities(tmp_path))

    assert discovery.roles == {
        "owner": (),
        "client": (
            BoundEntity("game", "code", "module of top-level public functions"),
        ),
    }
    assert discovery.not_applied is not None
    assert discovery.not_applied.startswith("owner not found: ")


def test_encapsulation_discovery_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "world.py").write_text(_WORLD, encoding="utf-8")
    (tmp_path / "game.py").write_text(_GAME, encoding="utf-8")
    entities = _source_entities(tmp_path)

    first = discover_roles("encapsulation", entities).to_dict()

    assert first == discover_roles("encapsulation", entities[::-1]).to_dict()


def test_abstract_methods_are_no_clients(tmp_path: Path) -> None:
    # Decorated with abstractmethod (whatever the body), or a body that only
    # raises NotImplementedError or is ... or pass after a docstring.
    (tmp_path / "tools.py").write_text(_STUBS, encoding="utf-8")

    discovery = discover_roles("encapsulation", _source_entities(tmp_path))

    # Tool is an interface (ABC): no case can build it, so even its concrete
    # label() is no client; Plain is no interface, its stubs are abstract.
    assert _names(discovery, "client") == ["tools.Plain.label"]


def test_container_built_later_and_inherited_makes_owners(tmp_path: Path) -> None:
    # The core's container rule: a comprehension built in initialize(), and
    # the same list for a subclass that changes it.
    (tmp_path / "rooms.py").write_text(_ROOMS, encoding="utf-8")

    discovery = discover_roles("encapsulation", _source_entities(tmp_path))

    assert discovery.roles["owner"] == (
        BoundEntity(
            "rooms.Shop",
            "code",
            "creates list items in initialize(), changed by add(), remove()",
        ),
    )
    assert discovery.not_applied is None


def test_augmented_assignment_is_a_change(tmp_path: Path) -> None:
    (tmp_path / "sack.py").write_text(_SACK, encoding="utf-8")

    discovery = discover_roles("encapsulation", _source_entities(tmp_path))

    assert discovery.roles["owner"] == (
        BoundEntity(
            "sack.Sack", "code", "creates list items in __init__, changed by add()"
        ),
    )


def test_container_changed_only_from_outside_makes_an_owner(tmp_path: Path) -> None:
    (tmp_path / "world.py").write_text(_OUTSIDE_WORLD, encoding="utf-8")
    (tmp_path / "actions.py").write_text(_OUTSIDE_ACTIONS, encoding="utf-8")

    discovery = discover_roles("encapsulation", _source_entities(tmp_path))

    assert discovery.roles["owner"] == (
        BoundEntity(
            "world.Inventory", "code", "container items changed from outside the class"
        ),
    )
    assert discovery.not_applied is None
    assert _names(discovery, "client") == ["actions"]


def test_test_modules_make_no_owner_and_no_client(tmp_path: Path) -> None:
    # Only the student's test changes the container from outside, and the
    # test's own functions would be clients: the tests are skipped.
    (tmp_path / "world.py").write_text(_OUTSIDE_WORLD, encoding="utf-8")
    (tmp_path / "test_world.py").write_text(
        "from world import State\n\n\n"
        + _OUTSIDE_ACTIONS.replace("def take", "def test_take"),
        encoding="utf-8",
    )

    discovery = discover_roles("encapsulation", _source_entities(tmp_path))

    assert discovery.roles["owner"] == ()
    assert "test_world" not in _names(discovery, "client")
    assert discovery.not_applied is not None


@pytest.mark.parametrize("change", ["popitem()", "sort()", "difference_update({1})"])
def test_every_mutating_method_of_the_core_is_a_change(
    tmp_path: Path, change: str
) -> None:
    container = (
        "{}" if change == "popitem()" else ("set()" if "update" in change else "[]")
    )
    (tmp_path / "bag.py").write_text(
        "class Bag:\n"
        f"    def __init__(self):\n        self.items = {container}\n\n"
        f"    def tidy(self):\n        self.items.{change}\n",
        encoding="utf-8",
    )

    discovery = discover_roles("encapsulation", _source_entities(tmp_path))

    assert _names(discovery, "owner") == ["bag.Bag"]
