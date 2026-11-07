"""N7: code in the style of a course whose game state lives in module globals.

A small text adventure: the sack and the current room are module globals of
``world`` (``SACK``, ``here``), their lists are made in ``reset()``, not in a
constructor, and every action gets only the words of the command. Two tasks
over it (encapsulation, logic apart from I/O) must be accepted without
handing the globals to the cases as arguments:

- the probe watches the project objects module globals hold, so a client
  that appends to ``world.SACK.things`` is caught (``held_by`` names the
  global);
- the mutation operators seed their errors into objects reached through a
  global (``world.here``, ``world.SACK``) and into containers a method other
  than ``__init__`` makes, of the class or of its project base;
- a role bound to a module also covers, statically, a function a student
  adds to it that no case runs.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pythonarchtesting.mcp_server.tasks import prepare_task

_WORLD = '''"""A tiny world: rooms, a sack and the things in them."""


class Thing:
    def __init__(self, name):
        self.name = name


class Holder:
    def __init__(self, names=()):
        self.start_names = tuple(names)

    def reset(self):
        self.things = [Thing(name) for name in self.start_names]

    def add(self, thing):
        self.things.append(thing)

    def pop(self, name):
        for index, thing in enumerate(self.things):
            if thing.name == name:
                return self.things.pop(index)
        return None


class Room(Holder):
    def __init__(self, name, exits, names=()):
        super().__init__(names)
        self.name = name
        self.exits = tuple(exits)


class Sack(Holder):
    def __init__(self, limit=2):
        super().__init__()
        self._limit = limit

    def try_add(self, thing):
        if len(self.things) >= self._limit:
            return False
        self.add(thing)
        return True


ROOMS = {
    "hall": Room("hall", ["yard"], ["lamp", "key"]),
    "yard": Room("yard", ["hall"]),
}
here: Room = None
SACK = Sack()


def initialize():
    global here
    SACK.reset()
    for room in ROOMS.values():
        room.reset()
    here = ROOMS["hall"]
'''

_ACTIONS = '''"""What the player can do: each action gets the words of the command."""
from . import world


def take(words):
    if len(words) < 2:
        return "Take what?"
    thing = world.here.pop(words[1])
    if thing is None:
        return "There is no " + words[1]
    if world.SACK.try_add(thing):
        return "Taken: " + thing.name
    world.here.add(thing)
    return "The sack is full"


def drop(words):
    if len(words) < 2:
        return "Drop what?"
    thing = world.SACK.pop(words[1])
    if thing is None:
        return "You do not carry " + words[1]
    world.here.add(thing)
    return "Dropped: " + thing.name


def start():
    world.initialize()
    return "Welcome"


def unknown(words):
    return "Unknown command " + words[0]


def go(words):
    if len(words) < 2:
        return "Go where?"
    if words[1] not in world.here.exits:
        return "No way to " + words[1]
    world.here = world.ROOMS[words[1]]
    return "You are in the " + words[1]
'''

_INIT = '''"""Text adventure: the user interface."""
from . import actions


def execute(command):
    words = command.lower().split()
    if not words:
        return actions.start()
    known = {"take": actions.take, "drop": actions.drop, "go": actions.go}
    return known.get(words[0], actions.unknown)(words)


def run():
    print(execute(""))
    while True:
        command = input("> ")
        if command == "end":
            print("Bye")
            return
        print(execute(command))
'''

# The cases start the world with ``world.initialize`` (the state lives in
# module globals, and the cases of a module run in one interpreter) and
# put a thing into the sack by its method; the globals themselves are never
# arguments.
_START = '{ "$new" = "world.initialize" }'
_CARRY = (
    '{ "$new" = "world.SACK.try_add", '
    'args = [{ "$new" = "world.Thing", args = ["lamp"] }] }'
)
_CASES = {
    "actions.take": [
        '{ args = [["take"]] }',
        f'{{ args = [[{_START}, "lamp"]] }}',
        f'{{ args = [[{_START}, "nothing"]] }}',
        f'{{ args = [[{_START}, "lamp", {_CARRY}, {_CARRY}]] }}',
    ],
    "actions.drop": [
        '{ args = [["drop"]] }',
        f'{{ args = [[{_START}, "lamp"]] }}',
        f'{{ args = [[{_START}, "lamp", {_CARRY}]] }}',
    ],
    "actions.go": [
        '{ args = [["go"]] }',
        f'{{ args = [[{_START}, "nowhere"]] }}',
        f'{{ args = [[{_START}, "yard"]] }}',
    ],
    "actions.start": ["{ args = [] }"],
    "actions.unknown": ['{ args = [["dance"]] }'],
    ".run": [
        '{ args = [], stdin = "take lamp\\nend\\n" }',
        '{ args = [], stdin = "go nowhere\\nend\\n" }',
    ],
    ".execute": [
        '{ args = [""] }',
        '{ args = ["take"] }',
        '{ args = ["drop lamp"] }',
        '{ args = ["go nowhere"] }',
        '{ args = ["dance"] }',
    ],
}
_ROLES = {
    "encapsulation": (
        'owner = ["world.Sack", "world.Room"]\nclient = ["actions.take", "actions.drop"]'
    ),
    "io_separation": 'logic = ["actions"]\nio = [".run", ".execute"]',
}


def write_task(task: Path, principle: str) -> Path:
    """The task of ``principle`` over the adventure, at ``task``."""
    reference = task / "reference" / "quest"
    reference.mkdir(parents=True)
    for name, text in (
        ("__init__.py", _INIT),
        ("world.py", _WORLD),
        ("actions.py", _ACTIONS),
    ):
        (reference / name).write_text(text, encoding="utf-8")
    bound = _ROLES[principle]
    names = [
        name
        for name in _CASES
        if name in bound or (name.startswith("actions.") and '"actions"' in bound)
    ]
    cases = "\n".join(f'"{name}" = [{", ".join(_CASES[name])}]' for name in names)
    (task / "task.toml").write_text(
        f'principle = "{principle}"\nreference = "reference/quest"\n\n'
        f"[roles]\n{bound}\n\n[cases]\n{cases}\n",
        encoding="utf-8",
    )
    return task


def _statuses(result: dict) -> dict[str, str]:
    return {e["error"]: e["status"] for e in result["errors"]}


def test_encapsulation_task_over_module_globals_is_accepted(tmp_path: Path) -> None:
    task = write_task(tmp_path / "enc", "encapsulation")

    result = prepare_task(str(task), sandbox="limits")

    assert result["problems"] == [], result
    # The sack and the room are reached through world.SACK and world.here,
    # their list ``things`` is made in Holder.reset(); no container is
    # private, so bypass_method has nothing to seed; the private ``_limit``
    # of the sack is written (replace_attribute) and read (read_private).
    assert _statuses(result) == {
        "bypass_method": "not_applicable",
        "mutate_container": "killed",
        "replace_attribute": "killed",
        "read_private": "killed",
    }, result
    assert result["accepted"] is True, result
    for entry in result["errors"]:
        if entry["status"] == "killed":
            assert entry["killed"] == entry["mutants"], entry


def test_io_task_over_module_globals_is_accepted(tmp_path: Path) -> None:
    task = write_task(tmp_path / "io", "io_separation")

    result = prepare_task(str(task), sandbox="limits")

    assert result["problems"] == [], result
    assert result["accepted"] is True, result


def _student(root: Path, name: str, actions: str, init: str = _INIT) -> None:
    package = root / name
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(init, encoding="utf-8")
    (package / "world.py").write_text(_WORLD, encoding="utf-8")
    (package / "actions.py").write_text(actions, encoding="utf-8")


@pytest.mark.parametrize("principle", ["encapsulation", "io_separation"])
def test_a_class_is_judged_by_the_globals_and_the_extra_actions(
    tmp_path: Path, principle: str
) -> None:
    from pythonarchtesting.mcp_server.evaluation import run_evaluation
    from pythonarchtesting.mcp_server.reports import explain_target

    task = write_task(tmp_path / "task", principle)
    students = tmp_path / "class"
    _student(students, "clean", _ACTIONS)
    # Appends to the sack's list past its method (and so past its limit).
    _student(
        students,
        "appender",
        _ACTIONS.replace(
            "    if world.SACK.try_add(thing):\n",
            "    world.SACK.things.append(thing)\n    if True:\n",
        ),
    )
    # An extra action no case runs (``execute`` does not even offer it)
    # prints instead of returning.
    _student(
        students,
        "shouter",
        _ACTIONS + '\n\ndef shout(words):\n    print("HEY!")\n    return ""\n',
    )
    # Renames the action whose check happened to carry the static scan of
    # the module and prints in it: the checks of the other actions still
    # read it.
    _student(
        students,
        "renamer",
        _ACTIONS.replace(
            "def drop(words):\n", 'def put_down(words):\n    print("dropping")\n'
        ),
        _INIT.replace("actions.drop", "actions.put_down"),
    )
    # Its own ``print`` (a stand-in for ``from rich import print``): the
    # extra action calls that, not the builtin.
    _student(
        students,
        "styler",
        _ACTIONS
        + "\n\ndef print(*args):\n    return None\n"
        + '\n\ndef shout(words):\n    print("HEY!")\n    return ""\n',
    )
    out = tmp_path / "out"

    report = run_evaluation(
        source=str(task),
        output_dir=str(out),
        targets_dir=str(students),
        dynamic=True,
        sandbox="limits",
    )

    verdicts = {}
    for name in ("clean", "appender", "shouter", "renamer", "styler"):
        explained = explain_target(report["report_json"], name, principle=principle)
        verdicts[name] = (
            explained["verdict"],
            [f["error_id"] for f in explained["findings"]],
            explained["findings"],
        )
    assert verdicts["clean"][:2] == ("passed", [])
    assert verdicts["styler"][:2] == ("passed", [])
    if principle == "encapsulation":
        assert verdicts["appender"][:2] == ("failed", ["mutate_container"])
        (finding,) = verdicts["appender"][2]
        assert finding["facts"]["held_by"] == "world.SACK"
        assert verdicts["shouter"][:2] == ("passed", [])
    else:
        assert verdicts["appender"][:2] == ("passed", [])
        assert verdicts["shouter"][:2] == ("failed", ["print_instead_of_return"])
        (finding,) = verdicts["shouter"][2]
        # The finding names the extra function, not the entity whose rule
        # carried the static part.
        assert "Function `shout` (actions.py:" in finding["what"], finding
        assert finding["facts"]["static"] is True
        # ``drop`` is bound by name, so its absence is a finding of its own;
        # the print in the renamed function is still found, once.
        assert verdicts["renamer"][:2] == (
            "failed",
            ["missing_required_entity", "print_instead_of_return"],
        )
        finding = verdicts["renamer"][2][1]
        assert "Function `put_down` (actions.py:" in finding["what"], finding
    shutil.rmtree(out)
