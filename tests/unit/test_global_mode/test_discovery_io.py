"""Role discovery for ``io_separation``: the input/output functions and the
logic, found in the code alone, and the one move the AI may make."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.global_mode.discovery import (
    ESSENTIAL_ROLES,
    Override,
    discover_roles,
)
from pythonarchtesting.global_mode.discovery.io_separation import (
    POSSIBLY_INPUT_IN_LOGIC,
)
from pythonarchtesting.global_mode.model import BoundEntity, RoleDiscovery
from pythonarchtesting.global_mode.selftask import _source_entities, write_self_task
from pythonarchtesting.principles.catalog import UnknownPrincipleError
from pythonarchtesting.principles.task import bind_task, load_task

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "global_mode"

_TAKE = """def take(state, words):
    crate = words[1] if len(words) > 1 else "box"
"""
_TAKE_WITH_INPUT = """def take(state, words):
    crate = input("Which crate? ")
"""


def _names(discovery: RoleDiscovery, role: str) -> list[str]:
    return [b.entity for b in discovery.roles[role]]


def _space_a_copy(tmp_path: Path, extra: str = "", take_reads: bool = False) -> Path:
    game = tmp_path / "space_a"
    shutil.copytree(FIXTURES / "space_a", game)
    actions = game / "actions.py"
    text = actions.read_text(encoding="utf-8")
    if take_reads:
        assert _TAKE in text
        text = text.replace(_TAKE, _TAKE_WITH_INPUT)
    actions.write_text(text + extra, encoding="utf-8")
    return game


def test_io_roles_of_space_a_match_expected() -> None:
    discovery = discover_roles("io_separation", _source_entities(FIXTURES / "space_a"))

    assert discovery.roles["io"] == (
        BoundEntity("ui.main", "code", "calls input(); called from the __main__ block"),
    )
    assert _names(discovery, "logic") == ["actions"]
    assert discovery.roles["logic"][0].source == "code"
    assert discovery.conflicts == ()
    assert discovery.not_applied is None


def test_io_roles_of_detective_b_match_expected() -> None:
    discovery = discover_roles(
        "io_separation", _source_entities(FIXTURES / "detective_b")
    )

    assert _names(discovery, "io") == ["console.run"]
    assert _names(discovery, "logic") == ["commands"]
    assert discovery.not_applied is None


def test_input_in_action_is_io_until_moved(tmp_path: Path) -> None:
    entities = _source_entities(_space_a_copy(tmp_path, take_reads=True))

    found = discover_roles("io_separation", entities)
    # take reads the keyboard: io; the rest of its module is bound function
    # by function, so that the module binding does not cover take, and only
    # what the io calls directly (through ui.COMMANDS): total_power, called
    # by status alone, is covered by the logic check of status.
    assert _names(found, "io") == ["actions.take", "ui.main"]
    assert _names(found, "logic") == [
        "actions.go",
        "actions.load",
        "actions.status",
    ]

    moved = discover_roles(
        "io_separation",
        entities,
        {"io": [Override("actions.take", "move", "logic", "a game action")]},
    )
    # ui.COMMANDS refers to take: the dispatcher calls it, so it is logic.
    assert _names(moved, "io") == ["ui.main"]
    assert "actions.take" in _names(moved, "logic")
    assert BoundEntity("actions.take", "ai", "a game action") in moved.roles["logic"]
    assert moved.conflicts == ()


# Reads the keyboard and calls project code (load): no pure input helper.
_ASK_NAME = '\n\ndef ask_name(state):\n    return load(state, [input("Name? ")])\n'


def test_move_rejected_for_unreferenced_function(tmp_path: Path) -> None:
    extra = _ASK_NAME
    entities = _source_entities(_space_a_copy(tmp_path, extra=extra))

    discovery = discover_roles(
        "io_separation",
        entities,
        {"io": [Override("actions.ask_name", "move", "logic", "an action")]},
    )

    assert "actions.ask_name" in _names(discovery, "io")
    assert "actions.ask_name" not in _names(discovery, "logic")
    assert discovery.conflicts == (
        "move of actions.ask_name from io to logic rejected: nothing in the "
        "project refers to it outside its own body",
    )


def test_move_other_than_io_to_logic_is_rejected() -> None:
    discovery = discover_roles(
        "io_separation",
        _source_entities(FIXTURES / "space_a"),
        {"logic": [Override("actions", "move", "io", "prints")]},
    )

    assert _names(discovery, "logic") == ["actions"]
    assert _names(discovery, "io") == ["ui.main"]
    assert discovery.conflicts == (
        "move of actions from logic to io rejected: only a move from io to "
        "logic of io_separation is allowed",
    )


def test_override_of_unknown_entity_is_a_conflict() -> None:
    discovery = discover_roles(
        "io_separation",
        _source_entities(FIXTURES / "space_a"),
        {
            "logic": [Override("actions.tkae", "add", None, "typo")],
            "io": [Override("ui.mian", "dispute", None, "typo")],
        },
    )

    assert _names(discovery, "logic") == ["actions"]
    assert _names(discovery, "io") == ["ui.main"]
    assert discovery.conflicts == (
        "add of actions.tkae to logic ignored: the submission has no such entity",
        "dispute of ui.mian in io ignored: the submission has no such entity",
    )


def test_ai_add_binds_with_source_ai_and_reports_two_roles() -> None:
    discovery = discover_roles(
        "io_separation",
        _source_entities(FIXTURES / "space_a"),
        {"logic": [Override("ui.main", "add", None, "it also computes")]},
    )

    assert BoundEntity("ui.main", "ai", "it also computes") in discovery.roles["logic"]
    assert _names(discovery, "io") == ["ui.main"]
    assert discovery.conflicts == ("ui.main fits more than one role: io, logic",)


def test_no_input_anywhere_is_not_applied(tmp_path: Path) -> None:
    (tmp_path / "calc.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    # No io calls calc, so it is no logic either: logic is what io calls.
    assert discovery.roles["io"] == ()
    assert discovery.roles["logic"] == ()
    assert discovery.not_applied is not None
    assert discovery.not_applied.startswith("io not found: ")


def test_discovery_is_deterministic(tmp_path: Path) -> None:
    entities = _source_entities(_space_a_copy(tmp_path, take_reads=True))
    overrides = {"io": [Override("actions.take", "dispute", None, "an action")]}

    first = discover_roles("io_separation", entities, overrides).to_dict()
    second = discover_roles("io_separation", list(reversed(entities)), overrides)

    assert first == second.to_dict()
    for bound in first["roles"].values():
        names = [b["entity"] for b in bound]
        assert names == sorted(names)


def test_essential_roles() -> None:
    assert ESSENTIAL_ROLES == {
        "io_separation": ("io", "logic"),
        "polymorphism": ("base", "variant"),
        "encapsulation": ("owner",),
        "strategy": ("context", "strategy"),
    }


def test_override_outside_the_rules_changes_nothing() -> None:
    discovery = discover_roles(
        "io_separation",
        _source_entities(FIXTURES / "space_a"),
        {
            "logic": [Override("ui.main", "dispute", None, "not logic")],
            "view": [Override("ui.main", "add", None, "a view")],
        },
    )

    assert _names(discovery, "io") == ["ui.main"]
    assert _names(discovery, "logic") == ["actions"]
    assert discovery.conflicts == (
        "add of ui.main to view ignored: io_separation has no role view",
        "dispute of ui.main in logic ignored: ui.main is not bound to logic",
    )


def test_principle_without_discovery_is_refused() -> None:
    with pytest.raises(ValueError, match="strategy"):
        discover_roles("strategy", [])
    with pytest.raises(UnknownPrincipleError):
        discover_roles("no_such_principle", [])


def test_entry_point_cannot_be_moved_to_logic() -> None:
    # ui.main is called only from the __main__ block: that is the entry point
    # itself, not a dispatcher calling it.
    discovery = discover_roles(
        "io_separation",
        _source_entities(FIXTURES / "space_a"),
        {"io": [Override("ui.main", "move", "logic", "it computes")]},
    )

    assert _names(discovery, "io") == ["ui.main"]
    assert _names(discovery, "logic") == ["actions"]
    assert discovery.conflicts == (
        "move of ui.main from io to logic rejected: nothing in the project "
        "refers to it outside its own body",
    )


def test_function_called_from_main_block_is_io(tmp_path: Path) -> None:
    (tmp_path / "game.py").write_text(
        "from rules import run\n\n\n"
        "def start():\n    return run(['look'])\n\n\n"
        "if __name__ == '__main__':\n    print(start())\n",
        encoding="utf-8",
    )
    (tmp_path / "rules.py").write_text(
        "def run(commands):\n    return len(commands)\n\n\n"
        "def score(points):\n    return points * 2\n",
        encoding="utf-8",
    )
    (tmp_path / "launcher.py").write_text(
        "from rules import score\n\n"
        "if __name__ == '__main__':\n    print(score(3))\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    # start: defined beside the block; score: imported into it. Neither reads
    # the keyboard, both are entry points. run is only called by start.
    assert discovery.roles["io"] == (
        BoundEntity("game.start", "code", "called from the __main__ block"),
        BoundEntity("rules.score", "code", "called from the __main__ block"),
    )
    assert _names(discovery, "logic") == ["rules.run"]


_GAME = """from world import Player


class Game:
    def __init__(self):
        self.player = Player()
        self.commands = {"take": self.take, "look": self.look}

    def run(self):
        while True:
            line = input("> ")
            if line == "konec":
                break
            words = line.split()
            print(self.commands[words[0]](words))

    def take(self, words):
        self.player.items.append(words[1])
        return "taken"

    def look(self, words):
        return ", ".join(self.player.inventory())

    def ask_name(self):
        return input("name? ")


if __name__ == "__main__":
    Game().run()
"""

_WORLD = """class Player:
    def __init__(self):
        self.items = []

    def inventory(self):
        return list(self.items)
"""


def test_pure_oo_game_binds_dispatched_methods_as_logic(tmp_path: Path) -> None:
    (tmp_path / "game.py").write_text(_GAME, encoding="utf-8")
    (tmp_path / "world.py").write_text(_WORLD, encoding="utf-8")
    entities = _source_entities(tmp_path)

    discovery = discover_roles("io_separation", entities)

    # ask_name only reads the keyboard: a pure input helper, in no role.
    assert _names(discovery, "io") == ["game.Game.run"]
    # The actions are methods the io method dispatches through a dict.
    assert _names(discovery, "logic") == ["game.Game.look", "game.Game.take"]
    assert discovery.not_applied is None

    roles = {role: _names(discovery, role) for role in ("io", "logic")}
    cases: dict[str, list[Any]] = {
        "game.Game.look": [{"args": [["look"]]}],
        "game.Game.take": [{"args": [["take", "key"]]}],
        "game.Game.run": [{"args": [], "stdin": "look\nkonec\n"}],
    }
    task = write_self_task(tmp_path, "io_separation", roles, cases, tmp_path / ".task")
    assert task.dropped == ()
    bind_task(load_task(task.task_dir), entities)


def test_pure_helpers_beside_io_are_in_no_role(tmp_path: Path) -> None:
    (tmp_path / "rules.py").write_text(
        "def score(cmd):\n    return len(cmd)\n", encoding="utf-8"
    )
    (tmp_path / "ui.py").write_text(
        "from rules import score\n\n\n"
        "def show_room(room):\n    print('You are in', room)\n\n\n"
        "def ask():\n    return input('> ')\n\n\n"
        "def main():\n"
        "    while True:\n"
        "        cmd = ask()\n"
        "        if cmd == 'q':\n            break\n"
        "        show_room(cmd)\n"
        "        print(score(cmd))\n\n\n"
        "if __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    # ask and show_room call no project code: pure input/output helpers,
    # neither io (they never call the logic) nor logic (input and output is
    # what they are for). main reads the keyboard through ask.
    assert discovery.roles["io"] == (
        BoundEntity(
            "ui.main",
            "code",
            "called from the __main__ block; reads input through ask()",
        ),
    )
    assert _names(discovery, "logic") == ["rules"]


def test_output_helper_calling_project_code_is_io(tmp_path: Path) -> None:
    (tmp_path / "rules.py").write_text(
        "def score(cmd):\n    return len(cmd)\n", encoding="utf-8"
    )
    (tmp_path / "ui.py").write_text(
        "from rules import score\n\n\n"
        "def show_score(cmd):\n    print('Score', score(cmd))\n\n\n"
        "def main():\n"
        "    while True:\n"
        "        cmd = input('> ')\n"
        "        if cmd == 'q':\n            break\n"
        "        show_score(cmd)\n\n\n"
        "if __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert discovery.roles["io"] == (
        BoundEntity("ui.main", "code", "calls input(); called from the __main__ block"),
        BoundEntity("ui.show_score", "code", "output helper beside the io"),
    )
    assert _names(discovery, "logic") == ["rules"]


def test_print_only_method_reached_by_io_is_in_no_role(tmp_path: Path) -> None:
    (tmp_path / "game.py").write_text(
        "from view import View\nfrom world import Room\n\n\n"
        "class Game:\n"
        "    def __init__(self):\n"
        "        self.view = View()\n        self.room = Room('hall')\n\n"
        "    def run(self):\n"
        "        while True:\n"
        "            cmd = input('> ')\n"
        "            if cmd == 'q':\n                break\n"
        "            self.view.render(self.room)\n"
        "            self.room.enter(cmd)\n\n\n"
        "if __name__ == '__main__':\n    Game().run()\n",
        encoding="utf-8",
    )
    (tmp_path / "view.py").write_text(
        "class View:\n"
        "    def render(self, room):\n        print('You are in', room.name)\n",
        encoding="utf-8",
    )
    (tmp_path / "world.py").write_text(
        "class Room:\n"
        "    def __init__(self, name):\n        self.name = name\n\n"
        "    def enter(self, cmd):\n        self.name = cmd\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    # render prints and calls nothing of the project: a pure output helper.
    # Game().run() in the __main__ block makes run an entry point.
    assert discovery.roles["io"] == (
        BoundEntity(
            "game.Game.run", "code", "calls input(); called from the __main__ block"
        ),
    )
    assert discovery.roles["logic"] == (
        BoundEntity(
            "world.Room.enter",
            "code",
            "method the io game.Game.run calls or dispatches",
        ),
    )


def test_data_dict_value_is_not_a_dispatch(tmp_path: Path) -> None:
    (tmp_path / "game.py").write_text(
        "from world import Hero\n\n\n"
        "def main():\n"
        "    hero = Hero('Ann')\n"
        "    while True:\n"
        "        cmd = input('> ')\n"
        "        if cmd == 'q':\n            break\n"
        "        name = cmd\n"
        "        state = {'name': name, 'hero': hero.n}\n"
        "        print(state)\n\n\n"
        "if __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    (tmp_path / "world.py").write_text(
        "class Hero:\n"
        "    def __init__(self, n):\n        self.n = n\n\n"
        "    def name(self):\n        print('I am', self.n)\n        return self.n\n\n"
        "    def n_items(self):\n        return []\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    # name is a local variable and hero.n an attribute, not a method of a
    # project class: neither is a dispatched action.
    assert _names(discovery, "io") == ["game.main"]
    assert discovery.roles["logic"] == ()


def test_dispatched_action_that_reads_input_is_disputed_io(tmp_path: Path) -> None:
    # take reads the keyboard and ui.COMMANDS dispatches it as an action:
    # it stays io (the code cannot tell), but is flagged for the AI and
    # the teacher as possibly input_in_logic.
    entities = _source_entities(_space_a_copy(tmp_path, take_reads=True))

    found = discover_roles("io_separation", entities)

    take = next(b for b in found.roles["io"] if b.entity == "actions.take")
    assert take.source == "code"
    assert take.disputed is not None
    assert take.disputed.startswith("possibly input_in_logic")
    main = next(b for b in found.roles["io"] if b.entity == "ui.main")
    assert main.disputed is None


def test_unreferenced_input_function_is_not_disputed(tmp_path: Path) -> None:
    extra = _ASK_NAME
    entities = _source_entities(_space_a_copy(tmp_path, extra=extra))

    found = discover_roles("io_separation", entities)

    assert all(b.disputed is None for b in found.roles["io"])


def test_entry_points_of_the_fixtures_are_not_disputed() -> None:
    for name in ("space_a", "detective_b"):
        found = discover_roles("io_separation", _source_entities(FIXTURES / name))
        assert all(b.disputed is None for b in found.roles["io"]), name


# garden_c: a clean functional game in the shape students write: pure
# actions, a UI module with a command table, a pure parser and the input
# loop, and the entry point in a module of its own.
_ASK = """def ask():
    return input("> ").strip()
"""


def write_functional_game(root: Path, with_ask: bool = False) -> Path:
    """garden_c; ``with_ask`` reads the keyboard in ``ui.ask`` instead."""
    shutil.copytree(FIXTURES / "garden_c", root)
    if with_ask:
        ui = root / "ui.py"
        text = ui.read_text(encoding="utf-8")
        text = text.replace('line = input("> ")', "line = ask()")
        text = text.replace("def play(state):", _ASK + "\n\ndef play(state):")
        ui.write_text(text, encoding="utf-8")
    return root


def _disputed(root: Path) -> list[str]:
    found = discover_roles("io_separation", _source_entities(root))
    return [b.entity for b in found.roles["io"] if b.disputed is not None]


def test_input_loop_beside_a_pure_parser_is_not_disputed(tmp_path: Path) -> None:
    # ui.play reads the keyboard, sits beside the pure ui.parse and is called
    # by main.main: but it is a loop that dispatches the actions, UI by
    # construction.
    root = write_functional_game(tmp_path / "game")

    found = discover_roles("io_separation", _source_entities(root))

    assert _names(found, "io") == ["main.main", "ui.play"]
    assert "ui.parse" in _names(found, "logic")
    assert _disputed(root) == []


def test_ask_beside_a_parser_and_another_io_function_is_not_disputed(
    tmp_path: Path,
) -> None:
    root = write_functional_game(tmp_path / "game", with_ask=True)

    found = discover_roles("io_separation", _source_entities(root))
    # ask is a pure input helper (no role); play reads through it.
    assert _names(found, "io") == ["main.main", "ui.play"]
    assert "ui.ask" not in _names(found, "logic")
    assert _disputed(root) == []


def test_single_file_game_is_not_disputed(tmp_path: Path) -> None:
    game = write_functional_game(tmp_path / "game", with_ask=True)
    root = tmp_path / "single"
    root.mkdir()
    ui = (game / "ui.py").read_text(encoding="utf-8")
    (root / "game.py").write_text(
        (game / "actions.py").read_text(encoding="utf-8")
        + "\n\n"
        + ui.replace("import actions\n", "").replace("actions.", "")
        + '\n\nif __name__ == "__main__":\n    play(new_state())\n',
        encoding="utf-8",
    )

    found = discover_roles("io_separation", _source_entities(root))

    assert "game.play" in _names(found, "io")
    assert "game.ask" not in _names(found, "io") + _names(found, "logic")
    assert _disputed(root) == []


def test_oo_game_loop_dispatching_its_own_methods_is_not_disputed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "oo"
    root.mkdir()
    (root / "game.py").write_text(
        "class Game:\n"
        "    def __init__(self):\n"
        "        self.room = 'hall'\n"
        "        self.commands = {'go': self.go}\n\n"
        "    def go(self, room):\n"
        "        self.room = room\n"
        "        return 'You are in the ' + room\n\n"
        "    def run(self):\n"
        "        while True:\n"
        "            verb, _, arg = input('> ').partition(' ')\n"
        "            if verb == 'quit':\n"
        "                break\n"
        "            print(self.commands[verb](arg))\n",
        encoding="utf-8",
    )
    (root / "main.py").write_text(
        "from game import Game\n\n\ndef main():\n    Game().run()\n\n\n"
        "if __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )

    found = discover_roles("io_separation", _source_entities(root))

    assert "game.Game.run" in _names(found, "io")
    assert _disputed(root) == []


# Layered: ui calls game, game calls rules. Only game is what the io calls.
_LAYERED_UI = """from game import look, take


def main():
    while True:
        line = input("> ")
        if line == "quit":
            break
        print(look(line) if line == "look" else take(line))


if __name__ == "__main__":
    main()
"""
_LAYERED_GAME = """from rules import can_take


def look(where):
    return "You see " + where


def take(name):
    return "Taken." if can_take(name) else "No."
"""


def test_logic_is_what_the_io_calls_directly(tmp_path: Path) -> None:
    (tmp_path / "ui.py").write_text(_LAYERED_UI, encoding="utf-8")
    (tmp_path / "game.py").write_text(_LAYERED_GAME, encoding="utf-8")
    (tmp_path / "rules.py").write_text(
        "def can_take(name):\n    return name != ''\n", encoding="utf-8"
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    # rules is called by game only: the transitive logic check of game
    # covers it, and ui.main need not call it (require_runtime_calls).
    assert _names(discovery, "io") == ["ui.main"]
    assert _names(discovery, "logic") == ["game"]


def test_module_alias_and_attribute_calls_bind_the_module(tmp_path: Path) -> None:
    (tmp_path / "ui.py").write_text(
        "import game as g\n\n\n" "def main():\n    print(g.look(input('> ')))\n",
        encoding="utf-8",
    )
    (tmp_path / "game.py").write_text(_LAYERED_GAME, encoding="utf-8")
    (tmp_path / "rules.py").write_text(
        "def can_take(name):\n    return True\n", encoding="utf-8"
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "logic") == ["game"]


def test_input_helper_in_a_module_without_other_io_stays_io_and_disputed(
    tmp_path: Path,
) -> None:
    (tmp_path / "inputs.py").write_text(
        "def ask():\n    return input('> ').strip()\n\n\n"
        "def parse(line):\n    return line.split()\n",
        encoding="utf-8",
    )
    (tmp_path / "ui.py").write_text(
        "from inputs import ask, parse\nfrom game import look\n\n\n"
        "def main():\n    print(look(parse(ask())[0]))\n\n\n"
        "if __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    (tmp_path / "game.py").write_text(_LAYERED_GAME, encoding="utf-8")
    (tmp_path / "rules.py").write_text(
        "def can_take(name):\n    return True\n", encoding="utf-8"
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    # inputs has no other io entity and no entry point, so ask is no pure
    # helper: it stays io, and alone among logic it may be an action.
    assert _names(discovery, "io") == ["inputs.ask", "ui.main"]
    assert discovery.roles["io"][0].disputed == POSSIBLY_INPUT_IN_LOGIC
    assert discovery.roles["io"][1].disputed is None
    assert _names(discovery, "logic") == ["game", "inputs.parse"]


def test_input_action_called_by_name_from_an_if_elif_loop_is_disputed_io(
    tmp_path: Path,
) -> None:
    # pick reads the keyboard and calls nothing of the project, called by
    # name (no table) from the game loop of another module: no other io in
    # its module makes it a helper, so it stays io and may be an action.
    (tmp_path / "loop.py").write_text(
        "from moves import pick, inventory\n\n\n"
        "def run():\n"
        "    shelf = ['map', 'rope']\n"
        "    pack = []\n"
        "    while True:\n"
        "        word = input('? ')\n"
        "        if word == 'pick':\n"
        "            print(pick(shelf, pack))\n"
        "        elif word == 'inv':\n"
        "            print(inventory(pack))\n"
        "        elif word == 'end':\n"
        "            break\n\n\n"
        "if __name__ == '__main__':\n    run()\n",
        encoding="utf-8",
    )
    (tmp_path / "moves.py").write_text(
        "def pick(shelf, pack):\n"
        "    thing = input('Which? ')\n"
        "    if thing in shelf:\n"
        "        shelf.remove(thing)\n"
        "        pack.append(thing)\n"
        "        return 'Picked.'\n"
        "    return 'Not here.'\n\n\n"
        "def inventory(pack):\n    return ', '.join(pack)\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "io") == ["loop.run", "moves.pick"]
    assert discovery.roles["io"][0].disputed is None
    assert discovery.roles["io"][1].disputed == POSSIBLY_INPUT_IN_LOGIC
    assert _names(discovery, "logic") == ["moves.inventory"]

    moved = discover_roles(
        "io_separation",
        _source_entities(tmp_path),
        {"io": [Override("moves.pick", "move", "logic", "an action")]},
    )

    assert _names(moved, "io") == ["loop.run"]
    assert _names(moved, "logic") == ["moves.inventory", "moves.pick"]


@pytest.mark.parametrize(
    ("header", "lookup"),
    [
        ("from verbs import VERBS", "VERBS.get(parts[0])"),
        ("import verbs", "verbs.VERBS.get(parts[0])"),
        ("import verbs as v", "v.VERBS.get(parts[0])"),
    ],
)
def test_dispatch_table_imported_from_another_module_is_expanded(
    tmp_path: Path, header: str, lookup: str
) -> None:
    (tmp_path / "shell.py").write_text(
        f"{header}\n\n\n"
        "def main():\n"
        "    state = {'here': ['coin']}\n"
        "    while True:\n"
        "        parts = input('$ ').split()\n"
        "        if not parts:\n            return\n"
        f"        handler = {lookup}\n"
        "        print(handler(state) if handler else 'What?')\n\n\n"
        "if __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    (tmp_path / "verbs.py").write_text(
        "from deeds import grab, peek\n\nVERBS = {'grab': grab, 'peek': peek}\n",
        encoding="utf-8",
    )
    (tmp_path / "deeds.py").write_text(
        "def grab(state):\n    return state['here'].pop() if state['here'] else ''\n\n\n"
        "def peek(state):\n    return ' '.join(state['here'])\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "io") == ["shell.main"]
    assert _names(discovery, "logic") == ["deeds"]
    assert discovery.not_applied is None


_PRINTING_LOOP = (
    "from rules import pick, seen\n"
    "from screen import say, say_list\n\n\n"
    "def main():\n"
    "    shelf = ['map']\n"
    "    while True:\n"
    "        word = input('? ')\n"
    "        if word == 'pick':\n"
    "            say(pick(shelf))\n"
    "        elif word == 'see':\n"
    "            say_list(seen(shelf))\n"
    "        elif word == 'end':\n"
    "            break\n\n\n"
    "if __name__ == '__main__':\n    main()\n"
)
_RULES = (
    "def pick(shelf):\n    return shelf.pop() if shelf else 'nothing'\n\n\n"
    "def seen(shelf):\n    return list(shelf)\n"
)


def test_print_only_module_called_by_io_is_in_no_role(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(_PRINTING_LOOP, encoding="utf-8")
    (tmp_path / "rules.py").write_text(_RULES, encoding="utf-8")
    (tmp_path / "screen.py").write_text(
        "def say(text):\n    print(text)\n\n\n"
        "def say_list(things):\n    print('You see: ' + ', '.join(things))\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "io") == ["app.main"]
    assert _names(discovery, "logic") == ["rules"]


def test_printing_function_calling_project_code_stays_logic(
    tmp_path: Path,
) -> None:
    # say prints what rules.shout makes of its text: no output helper (it
    # calls project code), so the io's direct call binds it as logic.
    (tmp_path / "app.py").write_text(_PRINTING_LOOP, encoding="utf-8")
    (tmp_path / "rules.py").write_text(
        _RULES + "\n\ndef shout(text):\n    return text.upper()\n", encoding="utf-8"
    )
    (tmp_path / "screen.py").write_text(
        "from rules import shout\n\n\n"
        "def say(text):\n    print(shout(text))\n\n\n"
        "def say_list(things):\n    print('You see: ' + ', '.join(things))\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "io") == ["app.main"]
    assert _names(discovery, "logic") == ["rules", "screen.say"]


def test_print_only_action_that_changes_state_stays_logic(tmp_path: Path) -> None:
    # show only prints: an output helper. grab prints too and returns
    # nothing, but it changes the shelf: an action, so print_instead_of_return
    # is checked on it.
    (tmp_path / "app.py").write_text(
        "import deeds\n\n\n"
        "def main():\n"
        "    shelf = {'here': ['map'], 'pack': []}\n"
        "    while True:\n"
        "        word = input('? ')\n"
        "        if word == 'show':\n"
        "            deeds.show(shelf)\n"
        "        elif word == 'grab':\n"
        "            deeds.grab(shelf)\n"
        "        elif word == 'end':\n"
        "            break\n",
        encoding="utf-8",
    )
    (tmp_path / "deeds.py").write_text(
        "def show(shelf):\n    print('Here: ' + ', '.join(shelf['here']))\n\n\n"
        "def grab(shelf):\n"
        "    if shelf['here']:\n"
        "        shelf['pack'].append(shelf['here'].pop())\n"
        "        print('Grabbed.')\n"
        "    else:\n        print('Nothing.')\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "io") == ["app.main"]
    assert _names(discovery, "logic") == ["deeds.grab"]


@pytest.mark.parametrize(
    "body",
    [
        "    things.append(1)\n    print(things)\n",
        "    things[0] = 1\n    print(things)\n",
        "    del things[0]\n    print(things)\n",
        "    things.count = 1\n    print(things)\n",
        "    global SEEN\n    SEEN = 1\n    print(things)\n",
        "    LOG.append(things)\n    print(things)\n",
    ],
)
def test_print_only_function_that_mutates_is_no_output_helper(
    tmp_path: Path, body: str
) -> None:
    (tmp_path / "app.py").write_text(
        "from screen import say\n\n\n" "def main():\n    say([input('? ')])\n",
        encoding="utf-8",
    )
    (tmp_path / "screen.py").write_text(
        f"LOG = []\nSEEN = 0\n\n\ndef say(things):\n{body}", encoding="utf-8"
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "logic") == ["screen"]


def test_print_only_function_building_a_local_list_is_an_output_helper(
    tmp_path: Path,
) -> None:
    (tmp_path / "app.py").write_text(
        "from screen import say\nfrom rules import seen\n\n\n"
        "def main():\n    say(seen(input('? ')))\n",
        encoding="utf-8",
    )
    (tmp_path / "rules.py").write_text(
        "def seen(x):\n    return [x]\n", encoding="utf-8"
    )
    (tmp_path / "screen.py").write_text(
        "def say(things):\n"
        "    lines = []\n"
        "    for thing in things:\n        lines.append('- ' + thing)\n"
        "    print('\\n'.join(lines))\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "io") == ["app.main"]
    assert _names(discovery, "logic") == ["rules"]


_ASKING_MAIN = (
    "import deeds\nfrom prompts import ask\n\n\n"
    "def main():\n"
    "    shelf = ['map']\n"
    "    while True:\n"
    "        word = ask()\n"
    "        if word == 'see':\n            print(deeds.see(shelf))\n"
    "        elif word == 'end':\n            break\n\n\n"
    "if __name__ == '__main__':\n    main()\n"
)
_DEEDS = "def see(shelf):\n    return ', '.join(shelf)\n"


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    "prompts",
    [
        "def ask():\n    return input('> ').strip()\n",
        "def ask():\n    return input('> ').strip()\n\n\n"
        "def ask_yes(q):\n    return input(q + ' (y/n) ') == 'y'\n",
    ],
)
def test_input_helpers_in_a_module_without_logic_are_in_no_role(
    tmp_path: Path, prompts: str, reverse: bool
) -> None:
    (tmp_path / "app.py").write_text(_ASKING_MAIN, encoding="utf-8")
    (tmp_path / "deeds.py").write_text(_DEEDS, encoding="utf-8")
    (tmp_path / "prompts.py").write_text(prompts, encoding="utf-8")
    entities = _source_entities(tmp_path)

    discovery = discover_roles(
        "io_separation", list(reversed(entities)) if reverse else entities
    )

    assert _names(discovery, "io") == ["app.main"]
    assert _names(discovery, "logic") == ["deeds"]


@pytest.mark.parametrize("reverse", [False, True])
def test_two_input_actions_beside_logic_are_both_io(
    tmp_path: Path, reverse: bool
) -> None:
    # grab and drop both read the keyboard beside see: neither is a helper,
    # whatever the order of the entities.
    (tmp_path / "app.py").write_text(
        "import deeds\n\n\n"
        "def main():\n"
        "    shelf = {'here': ['map'], 'pack': []}\n"
        "    while True:\n"
        "        word = input('? ')\n"
        "        if word == 'grab':\n            print(deeds.grab(shelf))\n"
        "        elif word == 'drop':\n            print(deeds.drop(shelf))\n"
        "        elif word == 'see':\n            print(deeds.see(shelf))\n"
        "        elif word == 'end':\n            break\n",
        encoding="utf-8",
    )
    (tmp_path / "deeds.py").write_text(
        "def grab(shelf):\n"
        "    thing = input('Grab? ')\n"
        "    return 'ok' if thing in shelf['here'] else 'no'\n\n\n"
        "def drop(shelf):\n"
        "    thing = input('Drop? ')\n"
        "    return 'ok' if thing in shelf['pack'] else 'no'\n\n\n"
        "def see(shelf):\n    return ', '.join(shelf['here'])\n",
        encoding="utf-8",
    )
    entities = _source_entities(tmp_path)

    discovery = discover_roles(
        "io_separation", list(reversed(entities)) if reverse else entities
    )

    assert _names(discovery, "io") == ["app.main", "deeds.drop", "deeds.grab"]
    assert [b.disputed for b in discovery.roles["io"]] == [None, None, None]
    assert _names(discovery, "logic") == ["deeds.see"]


def test_printing_action_beside_one_that_returns_stays_logic(tmp_path: Path) -> None:
    # pick prints its result and returns nothing (print_instead_of_return),
    # but seen in its module returns a value: rules is logic, not UI.
    (tmp_path / "app.py").write_text(
        "from rules import pick, seen\n\n\n"
        "def main():\n"
        "    shelf = ['map']\n"
        "    while True:\n"
        "        word = input('? ')\n"
        "        if word == 'pick':\n"
        "            pick(shelf)\n"
        "        elif word == 'see':\n"
        "            print(seen(shelf))\n"
        "        elif word == 'end':\n"
        "            break\n",
        encoding="utf-8",
    )
    (tmp_path / "rules.py").write_text(
        "def pick(shelf):\n"
        "    if shelf:\n        print('Picked ' + shelf.pop())\n"
        "    else:\n        print('Nothing.')\n\n\n"
        "def seen(shelf):\n    return list(shelf)\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "io") == ["app.main"]
    assert _names(discovery, "logic") == ["rules"]


def test_printing_helper_reached_through_logic_stays_logic(tmp_path: Path) -> None:
    # check prints (output_through_helper) and returns a value; the io calls
    # only rules, which calls check: rules is logic, checked transitively.
    (tmp_path / "app.py").write_text(
        "from rules import pick\n\n\n"
        "def main():\n"
        "    shelf = ['map']\n"
        "    while True:\n"
        "        word = input('? ')\n"
        "        if word == 'end':\n            break\n"
        "        print(pick(shelf, word))\n",
        encoding="utf-8",
    )
    (tmp_path / "rules.py").write_text(
        "from guard import check\n\n\n"
        "def pick(shelf, word):\n"
        "    if check(shelf, word):\n        shelf.remove(word)\n"
        "        return 'Picked.'\n"
        "    return 'No.'\n",
        encoding="utf-8",
    )
    (tmp_path / "guard.py").write_text(
        "def check(shelf, word):\n"
        "    if word not in shelf:\n        print('There is no ' + word)\n"
        "    return word in shelf\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "io") == ["app.main"]
    assert _names(discovery, "logic") == ["rules"]


_OO_ASK = """from abc import ABC, abstractmethod


class Item(ABC):
    def __init__(self, name):
        self.name = name

    @abstractmethod
    def use(self, player):
        ...


class Key(Item):
    def use(self, player):
        return "click"


class Game:
    def __init__(self):
        self.items = [Key("key")]
        self.commands = {"use": self.use}

    def use(self, arg):
        return self.items[0].use(None)

    def execute(self, line):
        verb, _, arg = line.partition(" ")
        command = self.commands.get(verb)
        return command(arg) if command else "?"

    def ask(self):
        return input("> ")

    def run(self):
        while True:
            line = self.ask()
            if line == "quit":
                break
            print(self.execute(line))


if __name__ == "__main__":
    Game().run()
"""


def test_oo_game_reading_through_self_ask_is_an_entry_point(tmp_path: Path) -> None:
    (tmp_path / "game.py").write_text(_OO_ASK, encoding="utf-8")

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    # Game().run() in the __main__ block: an entry point; self.ask() is a
    # pure input helper, in no role.
    assert discovery.roles["io"] == (
        BoundEntity(
            "game.Game.run",
            "code",
            "called from the __main__ block; reads input through ask()",
        ),
    )
    # self.use in the dispatch dict is Game.use (the io method's family),
    # never the abstract Item.use nor Key.use of another family.
    assert _names(discovery, "logic") == ["game.Game.execute", "game.Game.use"]


def test_instance_in_main_block_and_inherited_method_are_entry_points(
    tmp_path: Path,
) -> None:
    (tmp_path / "game.py").write_text(
        "class Base:\n"
        "    def run(self):\n"
        "        print(self.step(input('> ')))\n\n"
        "    def step(self, line):\n        return line\n\n\n"
        "class Game(Base):\n"
        "    def step(self, line):\n        return line.upper()\n\n\n"
        "if __name__ == '__main__':\n"
        "    game = Game()\n"
        "    game.run()\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert discovery.roles["io"] == (
        BoundEntity(
            "game.Base.run", "code", "calls input(); called from the __main__ block"
        ),
    )
    # self.step in Base.run: the family of Base, Game's override included.
    assert _names(discovery, "logic") == ["game.Base.step", "game.Game.step"]


def test_io_call_matching_skips_abstract_and_interface_methods(
    tmp_path: Path,
) -> None:
    (tmp_path / "items.py").write_text(
        "from abc import ABC, abstractmethod\n\n\n"
        "class Item(ABC):\n"
        "    @abstractmethod\n    def use(self):\n        ...\n\n"
        "    def label(self):\n        return 'item'\n\n\n"
        "class Lamp(Item):\n"
        "    def use(self):\n        return 'light'\n",
        encoding="utf-8",
    )
    (tmp_path / "ui.py").write_text(
        "from items import Lamp\n\n\n"
        "def main():\n"
        "    lamp = Lamp()\n"
        "    if input('> ') == 'use':\n"
        "        print(lamp.use(), lamp.label())\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    # No case can build an Item: neither its abstract use nor its label is
    # bound; Lamp.use is.
    assert _names(discovery, "logic") == ["items.Lamp.use"]


@pytest.mark.parametrize(
    "path",
    ["test_game.py", "game_test.py", "conftest.py", "tests/helpers.py", "test/util.py"],
)
def test_test_modules_are_skipped(tmp_path: Path, path: str) -> None:
    (tmp_path / "ui.py").write_text(_LAYERED_UI, encoding="utf-8")
    (tmp_path / "game.py").write_text(_LAYERED_GAME, encoding="utf-8")
    (tmp_path / "rules.py").write_text(
        "def can_take(name):\n    return True\n", encoding="utf-8"
    )
    test = tmp_path / path
    test.parent.mkdir(parents=True, exist_ok=True)
    if test.parent != tmp_path:
        (test.parent / "__init__.py").write_text("", encoding="utf-8")
    test.write_text(
        "from game import take\n\n\n"
        "def check_take():\n    assert take(input('x')) == 'Taken.'\n\n\n"
        "if __name__ == '__main__':\n    check_take()\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "io") == ["ui.main"]
    assert _names(discovery, "logic") == ["game"]


@pytest.mark.parametrize(
    "body",
    [
        # an alias of an item of a parameter, then mutated
        "    pack = shelf['pack']\n    pack.append('x')\n    print(pack)\n",
        # an alias through another alias
        "    pack = shelf['pack']\n    held = pack\n    held.clear()\n    print(held)\n",
        # an item store through an alias
        "    pack = shelf['pack']\n    pack[0] = 'x'\n    print(pack)\n",
        # += on a parameter list changes it in place
        "    shelf['pack'] += ['x']\n    print(shelf)\n",
    ],
)
def test_mutation_through_an_alias_is_no_output_helper(
    tmp_path: Path, body: str
) -> None:
    (tmp_path / "app.py").write_text(
        "from screen import say\n\n\n"
        "def main():\n    say({'pack': [input('? ')]})\n",
        encoding="utf-8",
    )
    (tmp_path / "screen.py").write_text(f"def say(shelf):\n{body}", encoding="utf-8")

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "logic") == ["screen"]


def test_local_list_built_from_a_copy_is_no_mutation(tmp_path: Path) -> None:
    # sorted(...) and a literal build new lists: changing them changes
    # nothing the caller holds, and += on a local counter is arithmetic.
    (tmp_path / "app.py").write_text(
        "from screen import say\n\n\n"
        "def main():\n    say({'pack': [input('? ')]})\n",
        encoding="utf-8",
    )
    (tmp_path / "screen.py").write_text(
        "def say(shelf):\n"
        "    lines = sorted(shelf['pack'])\n"
        "    lines.append('--')\n"
        "    extra = ['end'] + []\n"
        "    extra.extend(lines)\n"
        "    count = 0\n"
        "    for line in extra:\n"
        "        count += 1\n"
        "        print(count, line)\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "io") == ["app.main"]
    assert discovery.roles.get("logic", ()) == ()


@pytest.mark.parametrize("reverse", [False, True])
def test_printing_method_helper_and_mutating_printing_method(
    tmp_path: Path, reverse: bool
) -> None:
    # Screen.show only prints: an output helper in no role. Store.grab prints
    # and changes the store: an action, logic.
    (tmp_path / "app.py").write_text(
        "from store import Store\nfrom screen import Screen\n\n\n"
        "class App:\n"
        "    def __init__(self):\n"
        "        self.store = Store()\n        self.screen = Screen()\n\n"
        "    def run(self):\n"
        "        while True:\n"
        "            word = input('? ')\n"
        "            if word == 'end':\n                break\n"
        "            self.screen.show(word)\n"
        "            self.store.grab(word)\n\n\n"
        "if __name__ == '__main__':\n    App().run()\n",
        encoding="utf-8",
    )
    (tmp_path / "screen.py").write_text(
        "class Screen:\n    def show(self, text):\n        print('> ' + text)\n",
        encoding="utf-8",
    )
    (tmp_path / "store.py").write_text(
        "class Store:\n"
        "    def __init__(self):\n        self.items = ['map']\n        self.pack = []\n\n"
        "    def grab(self, thing):\n"
        "        if thing in self.items:\n"
        "            self.items.remove(thing)\n"
        "            self.pack.append(thing)\n"
        "            print('Grabbed.')\n",
        encoding="utf-8",
    )
    entities = _source_entities(tmp_path)

    discovery = discover_roles(
        "io_separation", list(reversed(entities)) if reverse else entities
    )

    assert _names(discovery, "io") == ["app.App.run"]
    assert _names(discovery, "logic") == ["store.Store.grab"]


@pytest.mark.parametrize("reverse", [False, True])
def test_printing_helper_and_mutating_action_in_the_io_module(
    tmp_path: Path, reverse: bool
) -> None:
    # One file: banner only prints (UI); grab prints and changes the module's
    # shelf (an action, logic).
    (tmp_path / "game.py").write_text(
        "shelf = ['map']\npack = []\n\n\n"
        "def banner():\n    print('== Shop ==')\n\n\n"
        "def grab(thing):\n"
        "    if thing in shelf:\n"
        "        shelf.remove(thing)\n"
        "        pack.append(thing)\n"
        "        print('Grabbed.')\n\n\n"
        "def main():\n"
        "    banner()\n"
        "    while True:\n"
        "        word = input('? ')\n"
        "        if word == 'end':\n            break\n"
        "        grab(word)\n\n\n"
        "if __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    entities = _source_entities(tmp_path)

    discovery = discover_roles(
        "io_separation", list(reversed(entities)) if reverse else entities
    )

    assert _names(discovery, "io") == ["game.main"]
    assert _names(discovery, "logic") == ["game.grab"]


_SAY_CALLER = (
    "from screen import say\n\n\n"
    "def main():\n    say({'pack': [input('? ')]})\n\n\n"
    "if __name__ == '__main__':\n    main()\n"
)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    "body",
    [
        # an int accumulator fed from an item of a parameter
        "    total = 0\n"
        "    for thing in shelf['pack']:\n        total += len(thing)\n"
        "    print('Total:', total)\n",
        # a str accumulator
        "    line = 'Pack:'\n"
        "    for thing in shelf['pack']:\n        line += ' ' + thing\n"
        "    print(line)\n",
        # an accumulator fed from a global table
        "    worth = 0\n"
        "    for thing in shelf['pack']:\n        worth += PRICES.get(thing, 0)\n"
        "    print(worth)\n",
        # sort of a copy it built itself
        "    names = list(shelf['pack'])\n    names.sort()\n    print(names)\n",
    ],
)
def test_accumulators_and_sorted_copies_keep_an_output_helper(
    tmp_path: Path, body: str, reverse: bool
) -> None:
    (tmp_path / "app.py").write_text(_SAY_CALLER, encoding="utf-8")
    (tmp_path / "screen.py").write_text(
        f"PRICES = {{'map': 3}}\n\n\ndef say(shelf):\n{body}", encoding="utf-8"
    )
    entities = _source_entities(tmp_path)

    discovery = discover_roles(
        "io_separation", list(reversed(entities)) if reverse else entities
    )

    assert _names(discovery, "io") == ["app.main"]
    assert discovery.roles.get("logic", ()) == ()


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    "body",
    [
        # += on an alias of an item of a parameter extends it in place
        "    held = shelf['pack']\n    held += ['x']\n    print(held)\n",
        # += on a parameter
        "    shelf += {'x': 1}.items()\n    print(shelf)\n",
        # sort and reverse of a parameter's list
        "    shelf['pack'].sort()\n    print(shelf)\n",
        "    pack = shelf['pack']\n    pack.reverse()\n    print(pack)\n",
        # max() hands back one of the lists it was given, no new object
        "    longest = max([shelf['pack'], []], key=len)\n"
        "    longest.append('x')\n    print(longest)\n",
    ],
)
def test_augmented_or_sorting_change_of_a_non_local_is_a_mutation(
    tmp_path: Path, body: str, reverse: bool
) -> None:
    (tmp_path / "app.py").write_text(_SAY_CALLER, encoding="utf-8")
    (tmp_path / "screen.py").write_text(f"def say(shelf):\n{body}", encoding="utf-8")
    entities = _source_entities(tmp_path)

    discovery = discover_roles(
        "io_separation", list(reversed(entities)) if reverse else entities
    )

    assert _names(discovery, "logic") == ["screen"]


_UI_HELPERS = (
    "def ask():\n    return input('> ')\n\n\ndef say(text):\n    print(text)\n"
)
_TAKE_ONLY = "def take(item):\n    return 'took ' + item\n"
_RUN_LOOP = (
    "import actions\nimport ui\n\n\n"
    "def run():\n"
    "    while True:\n"
    "        command = ui.ask()\n"
    "        if command == 'q':\n"
    "            break\n"
    "        ui.say(actions.take(command))\n"
)


@pytest.mark.parametrize(
    "launcher",
    [
        # a module-alias call in the __main__ block
        {"main.py": "import game\n\nif __name__ == '__main__':\n    game.run()\n"},
        {"main.py": "import game as g\n\nif __name__ == '__main__':\n    g.run()\n"},
        # a call at the bottom of the module, without the guard
        {"game.py": _RUN_LOOP + "\n\nrun()\n"},
    ],
    ids=["alias", "alias_as", "unguarded"],
)
def test_entry_point_through_a_module_alias_or_without_a_guard(
    tmp_path: Path, launcher: dict[str, str]
) -> None:
    files = {"ui.py": _UI_HELPERS, "actions.py": _TAKE_ONLY, "game.py": _RUN_LOOP}
    for name, text in {**files, **launcher}.items():
        (tmp_path / name).write_text(text, encoding="utf-8")

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert discovery.not_applied is None
    assert discovery.roles["io"] == (
        BoundEntity(
            "game.run",
            "code",
            "called from the __main__ block; reads input through ask()",
        ),
    )
    assert _names(discovery, "logic") == ["actions"]


def test_game_loop_reading_through_a_helper_of_another_module_is_io(
    tmp_path: Path,
) -> None:
    (tmp_path / "ui.py").write_text(_UI_HELPERS, encoding="utf-8")
    (tmp_path / "actions.py").write_text(_TAKE_ONLY, encoding="utf-8")
    (tmp_path / "game.py").write_text(_RUN_LOOP, encoding="utf-8")
    (tmp_path / "main.py").write_text(
        "import game\n\n\ndef main():\n    game.run()\n\n\n"
        "if __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    # game.run is neither an entry point nor in a module that calls input():
    # it reads the keyboard through ui.ask, so it is io, not logic.
    assert _names(discovery, "io") == ["game.run", "main.main"]
    assert discovery.roles["io"][0].why == "reads input through ask()"
    assert _names(discovery, "logic") == ["actions"]


_SHOW_LOOP = (
    "from actions import take\nfrom display import show\n\n\n"
    "def main():\n"
    "    while True:\n"
    "        command = input()\n"
    "        if command == 'q':\n"
    "            break\n"
    "        show(take(command))\n\n\n"
    "if __name__ == '__main__':\n    main()\n"
)


@pytest.mark.parametrize(
    "display",
    [
        "def show(state):\n    for key, value in state.items():\n        print(key, value)\n",
        "def show(state):\n    print(state.get('took'), sorted(state.keys()))\n",
        "def show(state):\n    print('{}'.format(state))\n",
    ],
)
def test_project_method_named_like_a_builtin_method_keeps_an_output_helper(
    tmp_path: Path, display: str
) -> None:
    (tmp_path / "game.py").write_text(_SHOW_LOOP, encoding="utf-8")
    (tmp_path / "display.py").write_text(display, encoding="utf-8")
    (tmp_path / "actions.py").write_text(
        "def take(item):\n    return {'took': item}\n", encoding="utf-8"
    )
    # A project class with methods named like those of a dict or a str: the
    # display helper calls the builtin ones, nothing of the project.
    (tmp_path / "model.py").write_text(
        "class Inventory:\n"
        "    def items(self):\n        return []\n\n"
        "    def get(self, key):\n        return key\n\n"
        "    def keys(self):\n        return []\n\n"
        "    def format(self):\n        return ''\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "io") == ["game.main"]
    assert _names(discovery, "logic") == ["actions"]


def test_dotted_import_does_not_alias_the_package_to_the_module(
    tmp_path: Path,
) -> None:
    package = tmp_path / "space"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "actions.py").write_text(_TAKE_ONLY, encoding="utf-8")
    (tmp_path / "game.py").write_text(
        "import space.actions\n\n\n"
        "def main():\n"
        "    line = input()\n"
        "    print(space.take(line))\n\n\n"
        "if __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    entities = _source_entities(tmp_path)

    discovery = discover_roles("io_separation", entities)

    # space.take is no call of space.actions.take: the local name space is the
    # package, not its actions module.
    assert discovery.roles["logic"] == ()


def test_instance_method_called_at_the_bottom_of_the_module_is_an_entry_point(
    tmp_path: Path,
) -> None:
    (tmp_path / "game.py").write_text(
        "class Game:\n"
        "    def run(self):\n"
        "        print(self.step(input('> ')))\n\n"
        "    def step(self, line):\n        return line.upper()\n\n\n"
        "game = Game()\n"
        "game.run()\n",
        encoding="utf-8",
    )

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert discovery.roles["io"] == (
        BoundEntity(
            "game.Game.run", "code", "calls input(); called from the __main__ block"
        ),
    )
    assert _names(discovery, "logic") == ["game.Game.step"]


def test_move_rejected_when_only_an_unrelated_attribute_has_the_name(
    tmp_path: Path,
) -> None:
    # ui reads state.ask_name, an attribute of the state, not actions.ask_name.
    entities = _source_entities(
        _space_a_copy(
            tmp_path,
            extra=_ASK_NAME + "\n\ndef label(state):\n    return state.ask_name\n",
        )
    )

    discovery = discover_roles(
        "io_separation",
        entities,
        {"io": [Override("actions.ask_name", "move", "logic", "an action")]},
    )

    assert "actions.ask_name" not in _names(discovery, "logic")
    assert discovery.conflicts == (
        "move of actions.ask_name from io to logic rejected: nothing in the "
        "project refers to it outside its own body",
    )


@pytest.mark.parametrize(
    "body",
    [
        "    shelf.popitem()\n    print(shelf)\n",
        "    shelf['seen'].difference_update({'x'})\n    print(shelf)\n",
    ],
)
def test_every_mutating_method_of_the_core_makes_no_output_helper(
    tmp_path: Path, body: str
) -> None:
    (tmp_path / "app.py").write_text(_SAY_CALLER, encoding="utf-8")
    (tmp_path / "screen.py").write_text(f"def say(shelf):\n{body}", encoding="utf-8")

    discovery = discover_roles("io_separation", _source_entities(tmp_path))

    assert _names(discovery, "logic") == ["screen"]


def _flat_ui(root: Path, helpers: int) -> list[Any]:
    """A user interface of ``helpers`` output, input and action functions in
    one module, beside a logic module."""
    root.mkdir()
    lines = ["import logic", ""]
    for i in range(helpers):
        lines += [f"def show{i}(x):", "    print(x)", ""]
        lines += [f"def ask{i}():", "    return input('?')", ""]
        lines += [f"def act{i}(s):", f"    s.append({i})", "    return s", ""]
    lines += [
        "def main():",
        "    s = []",
        "    while True:",
        "        show0(logic.step(s, ask0()))",
        "",
        "if __name__ == '__main__':",
        "    main()",
    ]
    (root / "ui.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "logic.py").write_text(
        "def step(s, c):\n    s.append(c)\n    return s\n", encoding="utf-8"
    )
    return _source_entities(root)


def test_discovery_reads_each_function_once_not_once_per_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit 2026-11-08 § 3: the helper predicates asked whether a function
    reads input again for every helper of its module, so the work grew with
    the square of the module's size. Each function is now read once per
    discovery: twice the functions, about twice the reads."""
    from pythonarchtesting.global_mode.discovery import io_separation

    reads: list[int] = []
    original = io_separation.calls_input

    def counting(node: Any) -> bool:
        reads.append(1)
        return bool(original(node))

    monkeypatch.setattr(io_separation, "calls_input", counting)
    counts = []
    for helpers in (10, 20):
        entities = _flat_ui(tmp_path / f"ui{helpers}", helpers)
        reads.clear()
        discover_roles("io_separation", entities)
        counts.append(len(reads))

    assert counts[1] <= 2 * counts[0] + 10, counts
