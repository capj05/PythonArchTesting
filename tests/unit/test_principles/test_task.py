"""Tasks: ``task.toml`` binding a catalogue principle to an unannotated reference."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pythonarchtesting.config import load_config
from pythonarchtesting.matching.models import NAME_REQUIRED
from pythonarchtesting.principles.task import (
    TaskError,
    bind_task,
    is_task,
    load_task,
    needed_roles,
)
from pythonarchtesting.runner.source_prep import prepare_source

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib

_GRADES = """\
def parse_grades(text):
    return [int(word) for word in text.split()]


def average(grades):
    if not grades:
        raise ValueError("no grades")
    return sum(grades) / len(grades)


def _helper():
    return 1
"""
_APP = """\
from .grades import average, parse_grades


def main():
    print(average(parse_grades(input())))
"""
_TASK = """\
principle = "io_separation"

[roles]
logic = ["grades"]
io = ["app.main"]

[cases]
"grades.parse_grades" = [{ args = ["1 2"] }]
"grades.average" = [{ args = [[1, 2]] }, { args = [[]] }]
"app.main" = [{ args = [], stdin = "1 2\\n" }]
"""
# The same checks as markers, for the equivalence test.
_ANNOTATED_GRADES = """\
from typing import Annotated

from pythonarchtesting.rules import forbid_runtime_calls


def parse_grades(text):
    __archtest__: Annotated[
        None,
        forbid_runtime_calls(
            "builtins.print", "builtins.input", "io", transitive=True,
            cases=[{"args": ["1 2"]}],
        ),
    ]
    return [int(word) for word in text.split()]


def average(grades):
    __archtest__: Annotated[
        None,
        forbid_runtime_calls(
            "builtins.print", "builtins.input", "io", transitive=True,
            cases=[{"args": [[1, 2]]}, {"args": [[]]}],
        ),
    ]
    if not grades:
        raise ValueError("no grades")
    return sum(grades) / len(grades)


def _helper():
    return 1
"""
_ANNOTATED_APP = """\
from typing import Annotated

from pythonarchtesting.rules import require_runtime_calls

from .grades import average, parse_grades


def main():
    __archtest__: Annotated[
        None, require_runtime_calls("grades", cases=[{"args": [], "stdin": "1 2\\n"}])
    ]
    print(average(parse_grades(input())))
"""


def _reference(root: Path, grades: str = _GRADES, app: str = _APP) -> Path:
    reference = root / "reference"
    reference.mkdir(parents=True)
    (reference / "__init__.py").write_text("", encoding="utf-8")
    (reference / "grades.py").write_text(grades, encoding="utf-8")
    (reference / "app.py").write_text(app, encoding="utf-8")
    return reference


def _task(tmp_path: Path, text: str = _TASK) -> Path:
    task = tmp_path / "task"
    _reference(task)
    (task / "task.toml").write_text(text, encoding="utf-8")
    return task


def _config():
    return load_config(config_path=None, discover_from_cwd=False)


def _bind(task_dir: Path):
    task = load_task(task_dir)
    plain = prepare_source(config=_config(), source_path=task.reference)
    return bind_task(task, plain.source_entities)


def _problems(raised: pytest.ExceptionInfo[TaskError]) -> str:
    return "\n".join(raised.value.problems)


def test_a_task_binds_every_check_to_its_entities(tmp_path: Path) -> None:
    task_dir = _task(tmp_path)

    _, checks = _bind(task_dir)

    assert is_task(task_dir)
    # A module stands for its top-level public functions (not _helper).
    assert [(c.role, c.entity, c.marker) for c in checks] == [
        ("logic", "grades.average", "forbid_runtime_calls"),
        ("logic", "grades.parse_grades", "forbid_runtime_calls"),
        ("io", "app.main", "require_runtime_calls"),
    ]
    # target_role: the modules of the entities playing that role.
    assert checks[2].params["modules"] == ["grades"]
    assert checks[0].params["modules"] == ["builtins.print", "builtins.input", "io"]


def test_a_role_the_checks_need_must_be_bound(tmp_path: Path) -> None:
    text = _TASK.replace('io = ["app.main"]\n', "").replace(
        '"app.main" = [{ args = [], stdin = "1 2\\n" }]\n', ""
    )

    with pytest.raises(TaskError) as raised:
        load_task(_task(tmp_path, text))

    assert "role 'io' is not bound" in _problems(raised)
    assert "require_runtime_calls" in _problems(raised)


def test_a_target_role_alone_must_be_bound_too(tmp_path: Path) -> None:
    assert needed_roles(load_task(_task(tmp_path)).principle) == ["logic", "io"]


def test_an_unknown_entity_is_named(tmp_path: Path) -> None:
    task_dir = _task(tmp_path, _TASK.replace('io = ["app.main"]', 'io = ["app.run"]'))

    with pytest.raises(TaskError) as raised:
        _bind(task_dir)

    assert "[roles] 'io': the reference has no 'app.run'" in _problems(raised)


def test_missing_cases_name_the_entity_and_what_they_must_do(tmp_path: Path) -> None:
    text = _TASK.replace(
        '"grades.average" = [{ args = [[1, 2]] }, { args = [[]] }]\n', ""
    )

    with pytest.raises(TaskError) as raised:
        _bind(_task(tmp_path, text))

    assert "[cases] 'grades.average' is missing" in _problems(raised)
    assert "forbid_runtime_calls" in _problems(raised)


def test_cases_no_check_covers_are_an_error(tmp_path: Path) -> None:
    text = _TASK + '"grades._helper" = [{ args = [] }]\n'

    with pytest.raises(TaskError) as raised:
        _bind(_task(tmp_path, text))

    assert "[cases] 'grades._helper': no check of the task covers it" in _problems(
        raised
    )


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('principle = "io_separation"', 'principle = "io_sep"', "unknown principle"),
        ('logic = ["grades"]', 'logic = ["grades"]\nowner = ["x"]', "not a role of"),
        ('logic = ["grades"]', "logic = []", "[roles] 'logic' binds no entity"),
        ("[roles]", 'colour = "blue"\n\n[roles]', "unknown key 'colour'"),
        (
            'principle = "io_separation"',
            'principle = "io_separation"\nreference = "x"',
            "does not exist",
        ),
    ],
)
def test_malformed_task_toml_is_a_clear_error(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    assert old in _TASK
    with pytest.raises(TaskError) as raised:
        load_task(_task(tmp_path, _TASK.replace(old, new, 1)))

    assert message in _problems(raised)
    assert "task.toml" in str(raised.value)


def test_a_module_without_public_functions_is_an_error(tmp_path: Path) -> None:
    task_dir = _task(tmp_path, _TASK.replace('io = ["app.main"]', 'io = ["empty"]'))
    (task_dir / "reference" / "empty.py").write_text("X = 1\n", encoding="utf-8")

    with pytest.raises(TaskError) as raised:
        _bind(task_dir)

    assert "module 'empty' has no top-level public function" in _problems(raised)


def test_a_reference_with_its_own_markers_is_refused(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    _reference(task_dir, _ANNOTATED_GRADES, _ANNOTATED_APP)
    (task_dir / "task.toml").write_text(_TASK, encoding="utf-8")

    with pytest.raises(TaskError) as raised:
        _bind(task_dir)

    assert "the reference carries markers of its own" in _problems(raised)


def _rules(state) -> list[tuple[str, str, str]]:
    return sorted(
        (r.rule_id, r.selector.source_entity_id, repr(sorted(r.params.items())))
        for r in state.rules
    )


def test_a_task_compiles_to_the_rules_of_the_equivalent_markers(
    tmp_path: Path,
) -> None:
    annotated = _reference(tmp_path / "annotated", _ANNOTATED_GRADES, _ANNOTATED_APP)
    task_dir = _task(tmp_path)

    from_markers = prepare_source(config=_config(), source_path=annotated)
    from_task = prepare_source(config=_config(), source_path=task_dir)

    assert len(from_task.rules) == 3
    assert _rules(from_task) == _rules(from_markers)
    assert from_task.compiler_validations == []
    # The run reads the reference; the task's principle is recorded.
    assert from_task.source_path == task_dir / "reference"
    assert from_task.principle == "io_separation"
    assert from_markers.principle is None


def test_the_reference_files_are_not_touched(tmp_path: Path) -> None:
    task_dir = _task(tmp_path)
    before = {p: p.read_bytes() for p in (task_dir / "reference").rglob("*.py")}

    prepare_source(config=_config(), source_path=task_dir)

    assert {p: p.read_bytes() for p in (task_dir / "reference").rglob("*.py")} == before


def test_a_class_method_and_init_are_bound(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    reference = task_dir / "reference"
    reference.mkdir(parents=True)
    (reference / "__init__.py").write_text("", encoding="utf-8")
    (reference / "shop.py").write_text(
        "class Shop:\n    def __init__(self):\n        self.n = 0\n\n"
        "    def sell(self, item):\n        return item\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        'principle = "encapsulation"\n\n[roles]\nclient = ["shop.Shop.sell"]\n\n'
        '[cases]\n"shop.Shop.sell" = [{ args = ["x"] }]\n\n'
        '[init]\n"shop.Shop.sell" = { args = [] }\n',
        encoding="utf-8",
    )

    _, checks = _bind(task_dir)

    runtime, static = checks
    assert (runtime.entity, runtime.marker) == (
        "shop.Shop.sell",
        "forbid_foreign_writes",
    )
    assert runtime.params["init"] == {"args": []}
    # The static check on the same method runs nothing: no cases, no init.
    assert (static.entity, static.marker) == ("shop.Shop.sell", "forbid_private_access")
    assert static.params["cases"] is None and static.params["init"] is None


def test_a_static_check_is_declared_without_cases(tmp_path: Path) -> None:
    """The client's static check (``forbid_private_access``) is declared
    without cases beside its runtime one, which takes the entity's cases."""
    task_dir = tmp_path / "task"
    reference = task_dir / "reference"
    reference.mkdir(parents=True)
    (reference / "__init__.py").write_text("", encoding="utf-8")
    (reference / "shop.py").write_text(
        "class Shop:\n    def __init__(self):\n        self._n = 0\n\n"
        "    def count(self):\n        return self._n\n\n\n"
        "def show(shop: Shop):\n    return shop.count()\n",
        encoding="utf-8",
    )
    (task_dir / "task.toml").write_text(
        'principle = "encapsulation"\n\n[roles]\nowner = ["shop.Shop"]\n'
        'client = ["shop.show"]\n\n'
        '[cases]\n"shop.show" = [{ args = [{ "$new" = "shop.Shop" }] }]\n',
        encoding="utf-8",
    )

    entities, checks = _bind(task_dir)

    assert [(c.entity, c.marker) for c in checks] == [
        ("shop.show", "forbid_foreign_writes"),
        ("shop.show", "forbid_private_access"),
    ]
    [show] = [e for e in entities if e.qualname == "show"]
    kinds = [d.kind for d in show.annotation_declarations]
    assert kinds == ["forbid_foreign_writes", "forbid_private_access"]
    assert show.annotation_declarations[1].params == {}


def test_the_entities_a_role_binds_are_required_by_name(tmp_path: Path) -> None:
    entities, _ = _bind(_task(tmp_path))

    required = {
        f"{e.module_path}.{e.qualname}" for e in entities if e.extras.get(NAME_REQUIRED)
    }
    # Not _helper: no role binds it, so it keeps the usual matching.
    assert required == {"grades.parse_grades", "grades.average", "app.main"}


def test_an_unknown_entity_lists_the_closest_reference_entities(
    tmp_path: Path,
) -> None:
    task_dir = _task(tmp_path, _TASK.replace('io = ["app.main"]', 'io = ["app.mian"]'))

    with pytest.raises(TaskError) as raised:
        _bind(task_dir)

    assert "the reference has no 'app.mian'; the closest: app.main" in _problems(raised)


@pytest.mark.parametrize(
    ("cases", "message"),
    [
        ("[]", "cases must be a non-empty list of tables"),
        ('["1 2"]', "case 0 must be a table"),
        ('[{ args = ["1 2"], expected = 3 }]', "case 0 has unknown keys: expected"),
        ("[{ args = [nan] }]", "nan and inf are not case values"),
        ("[{ args = [[1, inf]] }]", "nan and inf are not case values"),
    ],
    ids=["empty", "not_a_table", "unknown_key", "nan", "inf"],
)
def test_invalid_cases_are_refused_when_the_task_is_bound(
    tmp_path: Path, cases: str, message: str
) -> None:
    old = '"grades.parse_grades" = [{ args = ["1 2"] }]'
    assert old in _TASK
    task_dir = _task(tmp_path, _TASK.replace(old, f'"grades.parse_grades" = {cases}'))

    with pytest.raises(TaskError) as raised:
        _bind(task_dir)

    assert f"[cases] 'grades.parse_grades': {message}" in _problems(raised)
    assert len(raised.value.problems) == 1


# A principle whose roles bind classes: the base is checked statically
# (``is_abstract_class``) and so are its variants (``subclass_of`` the class
# bound to ``base``, ``target_kind = "class"``); neither runs any case.
_HIERARCHY = """\
id = "hierarchy"
name = "Hierarchy"
level = "basic"
summary = "Variants share a base."
why = "Because."
errors = []

[roles]
base = "the base the variants share"
variant = "the variants"

[[checks]]
role = "base"
marker = "is_abstract_class"

[[checks]]
role = "variant"
marker = "subclass_of"
target_role = "base"
target_kind = "class"
"""

_SHAPES = """\
from abc import ABC, abstractmethod


class Shape(ABC):
    @abstractmethod
    def area(self):
        raise NotImplementedError


class Circle(Shape):
    def area(self):
        return 3


class Square(Shape):
    def area(self):
        return 4


def total(shapes):
    return sum(shape.area() for shape in shapes)
"""


def _hierarchy_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, roles: str
) -> Path:
    from pythonarchtesting.principles import task as task_module
    from pythonarchtesting.principles.catalog import parse_principle

    principle = parse_principle(tomllib.loads(_HIERARCHY), "hierarchy.toml")
    monkeypatch.setattr(task_module, "get_principle", lambda _: principle)
    task_dir = tmp_path / "task"
    reference = task_dir / "reference"
    reference.mkdir(parents=True)
    (reference / "__init__.py").write_text("", encoding="utf-8")
    (reference / "shapes.py").write_text(_SHAPES, encoding="utf-8")
    (task_dir / "task.toml").write_text(
        f'principle = "hierarchy"\n\n[roles]\n{roles}', encoding="utf-8"
    )
    return task_dir


_ROLES = 'base = ["shapes.Shape"]\nvariant = ["shapes.Circle", "shapes.Square"]\n'


def test_a_role_with_only_static_checks_needs_no_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, checks = _bind(_hierarchy_task(tmp_path, monkeypatch, _ROLES))

    assert [(c.entity, c.marker) for c in checks] == [
        ("shapes.Shape", "is_abstract_class"),
        ("shapes.Circle", "subclass_of"),
        ("shapes.Square", "subclass_of"),
    ]
    assert all(c.params["cases"] is None for c in checks)


def test_target_kind_class_resolves_single_class(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import Mock

    from pythonarchtesting.rules.compilation import compile_rules

    entities, checks = _bind(_hierarchy_task(tmp_path, monkeypatch, _ROLES))

    # The check gets the class bound to `base`, not its module.
    assert [c.params["modules"] for c in checks[1:]] == [["shapes.Shape"]] * 2
    [circle] = [e for e in entities if e.qualname == "Circle"]
    assert circle.annotation_declarations[0].params == {"base": "shapes.Shape"}
    rules, _, _ = compile_rules(entities, Mock())
    assert sorted(str(r.rule_id) for r in rules) == [
        "MOD001/is_abstract_class/v1",
        "NOM001/subclass_of/v1",
        "NOM001/subclass_of/v1",
    ]


def test_target_kind_class_rejects_multiple_classes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roles = 'base = ["shapes.Shape", "shapes.Circle"]\nvariant = ["shapes.Square"]\n'
    task_dir = _hierarchy_task(tmp_path, monkeypatch, roles)

    with pytest.raises(TaskError) as raised:
        _bind(task_dir)

    assert (
        "role 'base' binds 2 classes (shapes.Shape, shapes.Circle): subclass_of "
        "(role 'variant', target_kind 'class') needs exactly one class"
        in _problems(raised)
    )


@pytest.mark.parametrize(
    ("roles", "problem"),
    [
        # A function in a role a class marker covers: no invalid declaration
        # on the reference, a problem of the task.
        (
            'base = ["shapes.Shape"]\nvariant = ["shapes.Circle", "shapes.total"]\n',
            "[roles] 'variant': 'shapes.total' is a function, not a class; "
            "subclass_of checks classes: bind classes (module.Class)",
        ),
        (
            'base = ["shapes.total"]\nvariant = ["shapes.Circle"]\n',
            "[roles] 'base': 'shapes.total' is a function, not a class; "
            "is_abstract_class checks classes: bind classes (module.Class)",
        ),
        # Not silently dropped beside the one class either.
        (
            'base = ["shapes.Shape", "shapes.total"]\nvariant = ["shapes.Circle"]\n',
            "[roles] 'base': 'shapes.total' is a function, not a class",
        ),
        # A module stands for its functions, which are no classes.
        (
            'base = ["shapes"]\nvariant = ["shapes.Circle"]\n',
            "[roles] 'base': 'shapes.total' is a function, not a class",
        ),
        # The base among its own variants.
        (
            'base = ["shapes.Shape"]\nvariant = ["shapes.Shape", "shapes.Circle"]\n',
            "[roles] 'variant': 'shapes.Shape' is the class role 'base' binds; "
            "subclass_of needs the classes derived from it, not the class itself",
        ),
    ],
)
def test_a_class_role_binds_classes_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, roles: str, problem: str
) -> None:
    task_dir = _hierarchy_task(tmp_path, monkeypatch, roles)

    with pytest.raises(TaskError) as raised:
        _bind(task_dir)

    assert problem in _problems(raised)


def test_forbid_runtime_instantiation_targets_the_classes_of_its_role() -> None:
    """The strategy role binds classes: the check gets those classes, not
    their whole module (review of N5)."""
    example = Path(__file__).resolve().parents[3] / "example" / "principles"

    _, checks = _bind(example / "strategy")

    [instances] = [c for c in checks if c.marker == "forbid_runtime_instantiation"]
    assert instances.params["modules"] == [
        "discounts.NoDiscount",
        "discounts.PercentDiscount",
        "discounts.BulkDiscount",
    ]
    assert instances.not_applicable is None


def test_a_role_of_functions_leaves_forbid_runtime_instantiation_not_applicable(
    tmp_path: Path,
) -> None:
    task = tmp_path / "adventure"
    (task / "reference").mkdir(parents=True)
    (task / "reference" / "adventure.py").write_text(
        "class Action:\n"
        "    def __init__(self, execute):\n"
        "        self.execute = execute\n\n"
        "    def run(self, state):\n"
        "        return self.execute(state)\n\n\n"
        "def take(state):\n"
        "    return 'taken'\n",
        encoding="utf-8",
    )
    (task / "task.toml").write_text(
        'principle = "strategy"\n\n[roles]\ncontext = ["adventure.Action.run"]\n'
        'strategy = ["adventure.take"]\n\n[cases]\n'
        '"adventure.Action.run" = [{ args = [{ room = "hall" }] }]\n\n[init]\n'
        '"adventure.Action.run" = { args = [{ "$spy" = "strategy" }] }\n',
        encoding="utf-8",
    )

    entities, checks = _bind(task)

    [instances] = [c for c in checks if c.marker == "forbid_runtime_instantiation"]
    assert instances.not_applicable is not None
    assert "role 'strategy' binds no class" in instances.not_applicable
    # No declaration is made for it.
    [run] = [e for e in entities if e.qualname == "Action.run"]
    markers = {d.kind for d in run.annotation_declarations}
    assert "forbid_runtime_instantiation" not in markers
    assert "require_runtime_delegation" in markers
