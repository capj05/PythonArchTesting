"""Role discovery for ``polymorphism``: the base, its variants and the code
calling the base's methods, found in the code alone."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pythonarchtesting.entities import Entity
from pythonarchtesting.global_mode.discovery import (
    Override,
    discover_roles,
    split_by_base,
)
from pythonarchtesting.global_mode.model import BoundEntity, RoleDiscovery
from pythonarchtesting.global_mode.selftask import _source_entities, write_self_task
from pythonarchtesting.principles.task import bind_task, load_task

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "global_mode"

_ZOO = '''class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        """What the animal says."""
        raise NotImplementedError


class Dog(Animal):
    def speak(self):
        return "Woof"


class Cat(Animal):
    def speak(self):
        return "Meow"


class Keeper:
    def __init__(self, animals):
        self.animals = animals

    def feed(self):
        return [a.speak() for a in self.animals]


def chorus(animals):
    return " ".join(animal.speak() for animal in animals)
'''

_NO_CLASSES = """ROOMS = {"hall": ["kitchen"], "kitchen": ["hall"]}


def exits(room):
    return ROOMS.get(room, [])


def main():
    room = "hall"
    while True:
        line = input("> ")
        if line == "konec":
            break
        if line in exits(room):
            room = line
        print(room)


if __name__ == "__main__":
    main()
"""


_ITEMS = """class Item:
    def describe(self):
        return "item"


class Weapon(Item):
    def describe(self):
        return "weapon"


class Sword(Weapon):
    def describe(self):
        return "sword"


def show(things):
    return [t.describe() for t in things]
"""

_BOXES = """

class Box:
    def get(self):
        return 1


class Shelf(Box):
    def get(self):
        return 2


def count(boxes):
    return sum(b.get() for b in boxes)
"""


def _binds(submission: Path, discovery: RoleDiscovery, entities: list[Entity]) -> None:
    """The discovery's roles make a self-task the core accepts."""
    roles = {
        r: [b.entity for b in bound] for r, bound in discovery.roles.items() if bound
    }
    cases: dict[str, list[Any]] = {
        name: [{"args": [[]]}] for name in roles.get("client", [])
    }
    task = write_self_task(
        submission,
        "polymorphism",
        roles,
        cases,
        submission / ".task" / roles["base"][0],
    )
    bind_task(load_task(task.task_dir), entities)


def _names(discovery: RoleDiscovery, role: str) -> list[str]:
    return [b.entity for b in discovery.roles[role]]


def _zoo(tmp_path: Path) -> Path:
    (tmp_path / "zoo.py").write_text(_ZOO, encoding="utf-8")
    return tmp_path


def test_polymorphism_base_and_variants_of_space_a() -> None:
    discovery = discover_roles("polymorphism", _source_entities(FIXTURES / "space_a"))

    assert discovery.roles["base"] == (
        BoundEntity("ship.Module", "code", "abstract class with subclasses"),
    )
    assert discovery.roles["variant"] == (
        BoundEntity("ship.Reactor", "code", "subclass of ship.Module"),
        BoundEntity("ship.SolarPanel", "code", "subclass of ship.Module"),
    )
    assert discovery.roles["client"] == (
        BoundEntity(
            "actions.total_power", "code", "calls power() of ship.Module on an object"
        ),
    )
    assert discovery.conflicts == ()
    assert discovery.not_applied is None


def test_detective_b_polymorphism_not_applied() -> None:
    discovery = discover_roles(
        "polymorphism", _source_entities(FIXTURES / "detective_b")
    )

    assert discovery.roles["base"] == ()
    assert discovery.roles["variant"] == ()
    assert discovery.not_applied is not None
    assert discovery.not_applied.startswith("base not found: ")


def test_concrete_base_candidate_is_bound_as_base(tmp_path: Path) -> None:
    discovery = discover_roles("polymorphism", _source_entities(_zoo(tmp_path)))

    # Not abstract, yet it only raises NotImplementedError and has subclasses:
    # bound, so that the catalogue reports concrete_base.
    assert discovery.roles["base"] == (
        BoundEntity("zoo.Animal", "code", "concrete base candidate"),
    )
    assert _names(discovery, "variant") == ["zoo.Cat", "zoo.Dog"]
    assert _names(discovery, "client") == ["zoo.Keeper.feed", "zoo.chorus"]
    assert discovery.not_applied is None


def test_ai_cannot_remove_candidate_only_dispute(tmp_path: Path) -> None:
    entities = _source_entities(_zoo(tmp_path))

    disputed = discover_roles(
        "polymorphism",
        entities,
        {"base": [Override("zoo.Animal", "dispute", None, "a helper class")]},
    )
    assert disputed.roles["base"] == (
        BoundEntity(
            "zoo.Animal", "code", "concrete base candidate", disputed="a helper class"
        ),
    )
    assert disputed.conflicts == ()

    # There is no action that removes a candidate: anything but add, dispute
    # and move is recorded and changes nothing.
    removed = discover_roles(
        "polymorphism",
        entities,
        {"base": [Override("zoo.Animal", "remove", None, "not a base")]},  # type: ignore[arg-type]
    )
    assert removed.roles["base"] == (
        BoundEntity("zoo.Animal", "code", "concrete base candidate"),
    )
    assert removed.conflicts == (
        "remove of zoo.Animal in base ignored: an override may only add, "
        "dispute or move an entity",
    )

    moved = discover_roles(
        "polymorphism",
        entities,
        {"base": [Override("zoo.Animal", "move", "variant", "not a base")]},
    )
    assert _names(moved, "base") == ["zoo.Animal"]
    assert len(moved.conflicts) == 1


def test_abstract_intermediate_is_a_variant_of_the_topmost_base(
    tmp_path: Path,
) -> None:
    (tmp_path / "items.py").write_text(
        "from abc import ABC, abstractmethod\n\n\n"
        "class Named(ABC):\n"
        "    @abstractmethod\n"
        "    def name(self): ...\n\n\n"
        "class Item(Named, ABC):\n"
        "    @abstractmethod\n"
        "    def weight(self): ...\n\n\n"
        "class Key(Item):\n"
        "    def name(self):\n        return 'key'\n\n"
        "    def weight(self):\n        return 1\n\n\n"
        "def heaviest(items):\n    return max(i.weight() for i in items)\n",
        encoding="utf-8",
    )
    entities = _source_entities(tmp_path)

    discovery = discover_roles("polymorphism", entities)

    # One hierarchy, one base: the topmost one. The core's subclass_of
    # needs exactly one base class, and accepts an indirect subclass.
    assert discovery.roles["base"] == (
        BoundEntity("items.Named", "code", "abstract class with subclasses"),
    )
    assert discovery.roles["variant"] == (
        BoundEntity("items.Item", "code", "subclass of items.Named"),
        BoundEntity("items.Key", "code", "subclass of items.Named"),
    )
    # weight() is declared by the intermediate, still a method of the base's
    # hierarchy.
    assert _names(discovery, "client") == ["items.heaviest"]
    assert discovery.conflicts == ()
    _binds(tmp_path, discovery, entities)


def test_three_level_concrete_hierarchy_has_one_base(tmp_path: Path) -> None:
    (tmp_path / "world.py").write_text(_ITEMS, encoding="utf-8")
    entities = _source_entities(tmp_path)

    discovery = discover_roles("polymorphism", entities)

    assert discovery.roles["base"] == (
        BoundEntity("world.Item", "code", "concrete base candidate"),
    )
    assert discovery.roles["variant"] == (
        BoundEntity("world.Sword", "code", "subclass of world.Item"),
        BoundEntity("world.Weapon", "code", "subclass of world.Item"),
    )
    assert _names(discovery, "client") == ["world.show"]
    assert discovery.conflicts == ()
    assert split_by_base(discovery, entities) == [discovery]
    _binds(tmp_path, discovery, entities)


def test_independent_hierarchies_split_by_base(tmp_path: Path) -> None:
    (tmp_path / "world.py").write_text(_ITEMS + _BOXES, encoding="utf-8")
    entities = _source_entities(tmp_path)

    discovery = discover_roles(
        "polymorphism",
        entities,
        {"base": [Override("world.Box", "dispute", None, "a helper")]},
    )

    # Nothing is dropped from the discovery itself.
    assert _names(discovery, "base") == ["world.Box", "world.Item"]
    assert _names(discovery, "variant") == [
        "world.Shelf",
        "world.Sword",
        "world.Weapon",
    ]
    assert discovery.roles["client"] == (
        BoundEntity("world.count", "code", "calls get() of world.Box on an object"),
        BoundEntity(
            "world.show", "code", "calls describe() of world.Item on an object"
        ),
    )

    boxes, items = split_by_base(discovery, entities)
    assert boxes.roles == {
        "base": (
            BoundEntity(
                "world.Box", "code", "concrete base candidate", disputed="a helper"
            ),
        ),
        "variant": (BoundEntity("world.Shelf", "code", "subclass of world.Box"),),
        "client": (
            BoundEntity("world.count", "code", "calls get() of world.Box on an object"),
        ),
    }
    assert _names(items, "base") == ["world.Item"]
    assert _names(items, "variant") == ["world.Sword", "world.Weapon"]
    assert _names(items, "client") == ["world.show"]
    for part in (boxes, items):
        assert part.principle == "polymorphism"
        assert part.not_applied is None
        _binds(tmp_path, part, entities)


def test_project_without_classes_is_not_applied(tmp_path: Path) -> None:
    (tmp_path / "game.py").write_text(_NO_CLASSES, encoding="utf-8")
    entities = _source_entities(tmp_path)

    discovery = discover_roles("polymorphism", entities)

    assert discovery.roles == {"base": (), "variant": (), "client": ()}
    assert discovery.not_applied is not None
    assert discovery.not_applied.startswith("base not found: ")
    # The same project still has input/output apart from logic.
    io = discover_roles("io_separation", entities)
    assert _names(io, "io") == ["game.main"]
    assert _names(io, "logic") == ["game.exits"]


def test_polymorphism_discovery_is_deterministic(tmp_path: Path) -> None:
    entities = _source_entities(_zoo(tmp_path))

    first = discover_roles("polymorphism", entities).to_dict()

    assert first == discover_roles("polymorphism", entities[::-1]).to_dict()


def test_overridden_ordinary_class_is_a_concrete_base_candidate(tmp_path: Path) -> None:
    (tmp_path / "rooms.py").write_text(
        "class Room:\n"
        "    def describe(self):\n        return 'a room'\n\n\n"
        "class Cellar(Room):\n"
        "    def describe(self):\n        return 'a dark cellar'\n",
        encoding="utf-8",
    )

    discovery = discover_roles("polymorphism", _source_entities(tmp_path))

    # Not abstract, but a subclass overrides its method: bound, so that the
    # catalogue reports concrete_base instead of not applying the principle.
    assert discovery.roles["base"] == (
        BoundEntity("rooms.Room", "code", "concrete base candidate"),
    )
    assert discovery.roles["variant"] == (
        BoundEntity("rooms.Cellar", "code", "subclass of rooms.Room"),
    )
    assert discovery.not_applied is None


def test_subclass_overriding_only_init_makes_no_base(tmp_path: Path) -> None:
    (tmp_path / "items.py").write_text(
        "class Item:\n"
        "    def __init__(self, name):\n        self.name = name\n\n"
        "    def label(self):\n        return self.name\n\n\n"
        "class Key(Item):\n"
        "    def __init__(self):\n        super().__init__('key')\n\n"
        "    def unlock(self):\n        return True\n",
        encoding="utf-8",
    )

    discovery = discover_roles("polymorphism", _source_entities(tmp_path))

    assert discovery.roles["base"] == ()
    assert discovery.roles["variant"] == ()
    assert discovery.not_applied == (
        "base not found: no abstract class (ABC, @abstractmethod) has a "
        "subclass in the project, and no subclass overrides a method of its "
        "class (perhaps typical error not_a_subclass: a variant does not "
        "derive from the base class)"
    )


_PLAYER = """

class Player:
    def __init__(self):
        self.items = []

    def describe(self):
        return "a player"
"""


def test_ai_added_variant_is_placed_by_the_base_its_reason_names(
    tmp_path: Path,
) -> None:
    (tmp_path / "world.py").write_text(_ITEMS + _BOXES + _PLAYER, encoding="utf-8")
    entities = _source_entities(tmp_path)

    def parts(why: str) -> list[tuple[str, list[str], tuple[str, ...]]]:
        discovery = discover_roles(
            "polymorphism",
            entities,
            {"variant": [Override("world.Player", "add", None, why)]},
        )
        return [
            (part.roles["base"][0].entity, _names(part, "variant"), part.conflicts)
            for part in split_by_base(discovery, entities)
        ]

    unplaced = ("cannot attribute world.Player to a base",)
    # Player derives from no base: only a reason naming exactly one base by
    # its qualified name places it; else it is in no part, and every part
    # says so.
    assert parts("a kind of world.Item") == [
        ("world.Box", ["world.Shelf"], ()),
        ("world.Item", ["world.Player", "world.Sword", "world.Weapon"], ()),
    ]
    for why in (
        "missed by the code",
        "should derive from Item",
        "a world.Item kind, unlike world.Box",
    ):
        assert parts(why) == [
            ("world.Box", ["world.Shelf"], unplaced),
            ("world.Item", ["world.Sword", "world.Weapon"], unplaced),
        ], why


def test_ai_added_base_is_a_part_without_variants(tmp_path: Path) -> None:
    (tmp_path / "world.py").write_text(_ITEMS + _BOXES + _PLAYER, encoding="utf-8")
    entities = _source_entities(tmp_path)
    discovery = discover_roles(
        "polymorphism",
        entities,
        {"base": [Override("world.Player", "add", None, "AI base")]},
    )

    player = [
        part
        for part in split_by_base(discovery, entities)
        if part.roles["base"][0].entity == "world.Player"
    ]

    assert len(player) == 1
    assert player[0].roles["variant"] == ()
    # world.show calls describe(), which Player defines as well.
    assert _names(player[0], "client") == ["world.show"]
    assert player[0].not_applied is not None
    assert player[0].not_applied.startswith("variant not found: ")


_TOOLS = """from abc import ABC, abstractmethod


class Item(ABC):
    @abstractmethod
    def use(self, player):
        ...

    def update(self, turn):
        pass


class Potion(Item):
    def use(self, player):
        return player + 10


class Sword(Item):
    def use(self, player):
        return player - 1
"""


def test_method_no_variant_overrides_makes_no_client(tmp_path: Path) -> None:
    (tmp_path / "items.py").write_text(_TOOLS, encoding="utf-8")
    (tmp_path / "game.py").write_text(
        "def apply_all(things, player):\n"
        "    for t in things:\n        player = t.use(player)\n"
        "    return player\n\n\n"
        "def merge_scores(scores, extra):\n"
        "    scores.update(extra)\n    return scores\n",
        encoding="utf-8",
    )

    discovery = discover_roles("polymorphism", _source_entities(tmp_path))

    # update() is the base's own, no variant overrides it: calling it is no
    # use of the hierarchy's polymorphism, whatever the object is.
    assert discovery.roles["client"] == (
        BoundEntity("game.apply_all", "code", "calls use() of items.Item on an object"),
    )


_TICKING = """class Item:
    def update(self, turn):
        return turn


class Clock(Item):
    def update(self, turn):
        return turn + 1
"""


def test_receiver_that_is_obviously_a_builtin_makes_no_client(tmp_path: Path) -> None:
    (tmp_path / "items.py").write_text(_TICKING, encoding="utf-8")
    (tmp_path / "game.py").write_text(
        "SCORES = {}\n\n\n"
        "def tick(items, turn):\n"
        "    return [i.update(turn) for i in items]\n\n\n"
        "def record(extra):\n"
        "    SCORES.update(extra)\n\n\n"
        "def totals(extra):\n"
        "    seen = dict(extra)\n    seen.update({'x': 1})\n"
        "    names = set()\n    names.update(extra)\n"
        "    return seen, names\n\n\n"
        "class Board:\n"
        "    def __init__(self):\n        self.scores = {}\n\n"
        "    def add(self, extra):\n        self.scores.update(extra)\n",
        encoding="utf-8",
    )

    discovery = discover_roles("polymorphism", _source_entities(tmp_path))

    # update() is polymorphic here, but a dict or a set built by the code
    # is no object of the hierarchy.
    assert _names(discovery, "client") == ["game.tick"]
