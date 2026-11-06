"""Tasks: ``task.toml`` binding a catalogue principle to an unannotated reference."""

from __future__ import annotations

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

    [check] = checks
    assert (check.entity, check.marker) == ("shop.Shop.sell", "forbid_foreign_writes")
    assert check.params["init"] == {"args": []}


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
