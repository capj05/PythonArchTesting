"""M3: a task (``task.toml`` beside an unannotated reference) prepared and used.

``prepare_task`` on both example tasks accepts them, with every typical
error seeded by its operator and caught as that error; a
role the catalogue needs and the task leaves unbound fails clearly (Review
Focus 5); and ``run_evaluation`` takes the task directory as its source,
records its principle and judges the class by it.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import anyio
import pytest

from pythonarchtesting.mcp_server.reports import class_overview
from pythonarchtesting.mcp_server.tasks import prepare_task

_EXAMPLES = Path(__file__).resolve().parents[2] / "example" / "principles"
_COVERAGE = {
    "io_separation": {
        "print_instead_of_return": "killed",
        "input_in_logic": "killed",
        "output_through_helper": "killed",
        "file_io_in_logic": "killed",
        "logic_in_main": "killed",
    },
    "encapsulation": {
        "bypass_method": "killed",
        "mutate_container": "killed",
        "replace_attribute": "killed",
        "read_private": "killed",
    },
    "polymorphism": {
        "type_switch": "killed",
        "type_comparison": "killed",
        "not_a_subclass": "killed",
        "concrete_base": "killed",
    },
    "strategy": {
        "no_delegation": "killed",
        "hardcoded_strategy": "killed",
        "type_switch_on_strategy": "killed",
    },
}


def _files(root: Path) -> dict[Path, bytes]:
    return {
        path: path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


@pytest.mark.parametrize("principle", sorted(_COVERAGE))
def test_prepare_task_accepts_the_example_task(principle: str) -> None:
    task = _EXAMPLES / principle
    before = _files(task / "reference")
    before[task / "task.toml"] = (task / "task.toml").read_bytes()

    result = prepare_task(str(task), sandbox="limits")

    assert result["accepted"] is True, result
    assert result["principle"] == principle
    assert result["problems"] == []
    assert result["reference_passes"] is True
    assert result["checks"]
    for check in result["checks"]:
        assert check["cases_ran"] is True, check
        assert check["coverage"] >= 0.8, check
    assert {e["error"]: e["status"] for e in result["errors"]} == _COVERAGE[principle]
    for entry in result["errors"]:
        if entry["status"] == "killed":
            # Every mutant caught as this very error (its signature
            # matched): replace_attribute's mutants write the private _stock,
            # not a method attribute; bypass_method's change the contents of
            # _stock, mutate_container's those of the public log.
            assert entry["killed"] == entry["mutants"] > 0, entry
            assert entry["killed_other"] == 0, entry
            assert entry["signature_matched"] is True, entry
    # Nothing is written into the task.
    after = _files(task / "reference")
    after[task / "task.toml"] = (task / "task.toml").read_bytes()
    assert after == before


def test_prepare_task_names_a_role_the_task_leaves_unbound(tmp_path: Path) -> None:
    task = tmp_path / "encapsulation"
    shutil.copytree(
        _EXAMPLES / "encapsulation", task, ignore=shutil.ignore_patterns("assignments")
    )
    toml = task / "task.toml"
    text = toml.read_text(encoding="utf-8")
    toml.write_text(text.replace('client = ["shop"]\n', ""), encoding="utf-8")

    result = prepare_task(str(task), sandbox="limits")

    assert result["accepted"] is False
    assert result["checks"] == [] and result["errors"] == []
    assert any("role 'client' is not bound" in p for p in result["problems"])


def test_prepare_task_names_a_static_check_the_reference_fails(tmp_path: Path) -> None:
    """A static check runs no cases, so only its result on the reference can
    say why the task is not accepted: it is listed under ``problems``."""
    task = tmp_path / "polymorphism"
    shutil.copytree(
        _EXAMPLES / "polymorphism", task, ignore=shutil.ignore_patterns("assignments")
    )
    shapes = task / "reference" / "shapes.py"
    shapes.write_text(
        shapes.read_text(encoding="utf-8")
        + "\n\nclass Loose:\n    def area(self) -> float:\n        return 0.0\n",
        encoding="utf-8",
    )
    toml = task / "task.toml"
    text = toml.read_text(encoding="utf-8")
    toml.write_text(
        text.replace('"shapes.Square"]', '"shapes.Square", "shapes.Loose"]'),
        encoding="utf-8",
    )

    result = prepare_task(str(task), sandbox="limits")

    assert result["accepted"] is False
    assert result["reference_passes"] is False
    assert [p for p in result["problems"] if "Loose" in p], result["problems"]
    assert all("fails on the reference" in p for p in result["problems"])


class _Context:
    async def report_progress(self, *args: Any) -> None:
        return None


def test_run_evaluation_takes_the_task_as_its_source(tmp_path: Path) -> None:
    pytest.importorskip("mcp")
    from mcp.server.mcpserver.exceptions import ToolError

    from pythonarchtesting.mcp_server import server

    task = _EXAMPLES / "encapsulation"
    submissions = tmp_path / "submissions"
    for variant, student in (
        ("ok_basic", "xxxx01_novak"),
        ("err_sell_bypasses_remove", "xxxx02_dvorak"),
    ):
        shutil.copytree(task / "assignments" / variant, submissions / student)

    async def call(output_dir: Path, **extra: Any) -> dict[str, Any]:
        return await server.run_evaluation(
            _Context(),  # type: ignore[arg-type]
            source=str(task),
            output_dir=str(output_dir),
            targets_dir=str(submissions),
            sandbox="limits",
            **extra,
        )

    result = anyio.run(call, tmp_path / "out")

    # The task implies its principle: the run is dynamic and records it.
    assert result["principle"] == "encapsulation"
    assert result["dynamic_forced"] is True
    overview = class_overview(result["report_json"])
    assert overview["principle"] == "encapsulation"
    assert (overview["passed"], overview["failed"]) == (1, 1)
    # The variant also reads _stock (inventory._stock.get) before its write.
    assert list(overview["by_error"]) == ["bypass_method", "read_private"]
    with pytest.raises(ToolError, match="not the task's principle"):

        async def other() -> dict[str, Any]:
            return await call(tmp_path / "other", principle="io_separation")

        anyio.run(other)


def test_prepare_task_names_a_compiler_warning_among_its_problems(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A declaration the compiler refuses with a warning (compiler_invalid_param)
    keeps the task from being accepted, and says why. ``bind_task`` refuses
    such cases itself, so its check is switched off to reach the compiler."""
    from pythonarchtesting.principles import task as task_module

    monkeypatch.setattr(task_module, "_cases_problem", lambda *args: None)
    task = tmp_path / "io_separation"
    shutil.copytree(
        _EXAMPLES / "io_separation", task, ignore=shutil.ignore_patterns("assignments")
    )
    toml = task / "task.toml"
    old = '"grades.format_summary" = [{ args = [[1, 2, 3, 1]] }]'
    text = toml.read_text(encoding="utf-8")
    assert old in text
    toml.write_text(text.replace(old, old[:-3] + ", expected = 9 }]"), encoding="utf-8")

    result = prepare_task(str(task), sandbox="limits")

    assert result["accepted"] is False
    [problem] = result["problems"]
    assert problem.startswith("compiler_invalid_param on grades.format_summary:")
    assert "unknown keys: expected" in problem


def _variant(
    tmp_path: Path, principle: str, changes: list[tuple[str, str, str]]
) -> Path:
    """A copy of the example task with ``old`` replaced by ``new`` in each
    reference file named (``(file, old, new)``)."""
    task = tmp_path / principle
    shutil.copytree(
        _EXAMPLES / principle, task, ignore=shutil.ignore_patterns("assignments")
    )
    for name, old, new in changes:
        path = task / "reference" / name
        text = path.read_text(encoding="utf-8")
        assert old in text, (name, old)
        path.write_text(text.replace(old, new), encoding="utf-8")
    return task


@pytest.mark.parametrize(
    ("principle", "changes", "expected"),
    [
        # No public container: nothing for mutate_public_container anywhere,
        # which is no fault of the task.
        (
            "encapsulation",
            [
                ("inventory.py", "self.log: list[str] = []", "self.log_count = 0"),
                (
                    "inventory.py",
                    'self.log.append(f"+{quantity} {item}")',
                    "self.log_count += 1",
                ),
                (
                    "inventory.py",
                    'self.log.append(f"-{quantity} {item}")',
                    "self.log_count += 1",
                ),
            ],
            {"mutate_container": "not_applicable"},
        ),
        # A container built by a choice is one.
        (
            "encapsulation",
            [
                (
                    "inventory.py",
                    "self._stock: dict[str, int] = dict(stock or {})",
                    "self._stock = stock if stock is not None else {}",
                )
            ],
            {},
        ),
        # Unannotated parameters: the cases' $new say which is the inventory;
        # restock's deliveries (a dict, whose items() Inventory has too) is not.
        (
            "encapsulation",
            [
                ("shop.py", ": Inventory", ""),
                ("shop.py", "deliveries: dict[str, int]", "deliveries"),
            ],
            {},
        ),
        # A name-mangled container: the mutants write _Inventory__stock.
        ("encapsulation", [("inventory.py", "self._stock", "self.__stock")], {}),
        # A star import of the logic module.
        (
            "io_separation",
            [
                (
                    "app.py",
                    "from .grades import format_summary, parse_grades",
                    "from .grades import *",
                )
            ],
            {},
        ),
    ],
    ids=[
        "no_public_container",
        "ifexp_container",
        "unannotated",
        "mangled",
        "star_import",
    ],
)
def test_prepare_task_on_variants_of_the_reference(
    tmp_path: Path,
    principle: str,
    changes: list[tuple[str, str, str]],
    expected: dict[str, str],
) -> None:
    task = _variant(tmp_path, principle, changes)

    result = prepare_task(str(task), sandbox="limits")

    statuses = {e["error"]: e["status"] for e in result["errors"]}
    assert statuses == {error: expected.get(error, "killed") for error in statuses}
    assert result["accepted"] is True, result
    for entry in result["errors"]:
        if entry["status"] == "not_applicable":
            assert entry["why"].startswith("the reference contains no public container")
        else:
            assert entry["killed"] == entry["mutants"] > 0, entry
            assert entry["killed_other"] == 0, entry


def test_prepare_task_rejects_a_task_whose_operators_find_nothing(
    tmp_path: Path,
) -> None:
    """``client`` bound to a function that gets no object of a project class
    (``banner(title: str)``): the operators find nothing to change in the
    entities the checks are on, so the errors are ``no_mutants`` and the task
    is not accepted: its binding cannot show that the checks catch them."""
    task = _variant(
        tmp_path,
        "encapsulation",
        [
            (
                "shop.py",
                "def report(",
                "def banner(title: str) -> str:\n"
                "    return title.upper()\n\n\n"
                "def report(",
            )
        ],
    )
    toml = task / "task.toml"
    text = toml.read_text(encoding="utf-8")
    text = text.replace('client = ["shop"]', 'client = ["shop.banner"]')
    text = text[: text.index("[cases]")] + (
        '[cases]\n"shop.banner" = [{ args = ["sale"] }, { args = [""] }]\n'
    )
    toml.write_text(text, encoding="utf-8")

    result = prepare_task(str(task), sandbox="limits")

    assert result["problems"] == []
    assert result["accepted"] is False, result
    # The checks themselves run: only the errors stop the task.
    assert all(check["accepted"] for check in result["checks"]), result
    assert {e["error"]: e["status"] for e in result["errors"]} == {
        error: "no_mutants" for error in _COVERAGE["encapsulation"]
    }
    for entry in result["errors"]:
        assert "found nothing to change" in entry["why"], entry


_ADVENTURE = """\
from __future__ import annotations

from typing import Callable


class Log:
    def __init__(self) -> None:
        self.lines: list[str] = []


class Action:
    def __init__(self, name: str, description: str, execute: Callable[[dict], str]) -> None:
        self.name = name
        self.description = description
        self.execute = execute
        self.log = Log()

    def run(self, state: dict) -> str:
        result = self.execute(state)
        self.log.lines.append(result)
        return f"{self.name}: {result}"


def take(state: dict) -> str:
    state["items"] = state.get("items", 0) + 1
    return "taken"


def look(state: dict) -> str:
    return "you see a room"
"""
_ADVENTURE_TASK = """\
principle = "strategy"

[roles]
context = ["adventure.Action.run"]
strategy = ["adventure.take", "adventure.look"]

[cases]
"adventure.Action.run" = [{ args = [{ room = "hall" }] }]

[init]
"adventure.Action.run" = { args = ["take", "Take an item", { "$spy" = "strategy" }] }
"""


def test_prepare_task_accepts_strategies_written_as_functions(tmp_path: Path) -> None:
    """The text adventure of the course: the strategy is a function an action
    is given and calls (``self.execute(state)``), in a flat reference. The
    context builds a ``Log`` of its own, which is no strategy: the strategy
    role binds no class, so nothing it builds can be one and
    ``hardcoded_strategy`` is not applicable; ``no_delegation`` is verified
    by cutting the call of the function (review of N5)."""
    task = tmp_path / "adventure"
    (task / "reference").mkdir(parents=True)
    (task / "reference" / "adventure.py").write_text(_ADVENTURE, encoding="utf-8")
    (task / "task.toml").write_text(_ADVENTURE_TASK, encoding="utf-8")

    result = prepare_task(str(task), sandbox="limits")

    # Accepted, with a warning: the module also has classes (Log, Action),
    # so the teacher's AI sees why building one is not checked.
    [warning] = result["problems"]
    assert warning.startswith("WARNING: role 'strategy' binds only functions")
    assert "adventure.Log" in warning and "not_applicable" in warning
    assert result["accepted"] is True, result
    statuses = {e["error"]: e for e in result["errors"]}
    assert statuses["no_delegation"]["status"] == "killed"
    assert statuses["no_delegation"]["signature_matched"] is True
    assert statuses["hardcoded_strategy"]["status"] == "not_applicable"
    assert "binds no class" in statuses["hardcoded_strategy"]["why"]
    [instances] = [
        c for c in result["checks"] if c["marker"] == "forbid_runtime_instantiation"
    ]
    assert instances["status"] == "not_applicable"
    assert "binds no class" in instances["why"]


@pytest.mark.parametrize(
    ("changes", "mutants"),
    [
        # An annotated assignment keeps the strategy too.
        (
            [
                (
                    "pricing.py",
                    "self.discount = discount",
                    "self.discount: Discount = discount",
                )
            ],
            1,
        ),
        # A second constructor parameter the task gives no spy is no strategy.
        (
            [
                (
                    "pricing.py",
                    "discount: Discount) -> None:",
                    "discount: Discount, vat: float = 0.0) -> None:",
                ),
                (
                    "pricing.py",
                    "self.discount = discount",
                    "self.discount = discount\n        self.vat = vat",
                ),
            ],
            1,
        ),
        # A context that inherits its constructor from a project base (review
        # of the N5 fix round): the spy is kept by the base's __init__.
        (
            [
                (
                    "pricing.py",
                    "class PriceCalculator:\n",
                    "class Calculator:\n",
                ),
                (
                    "pricing.py",
                    "        self.discount = discount\n",
                    "        self.discount = discount\n\n\n"
                    "class PriceCalculator(Calculator):\n",
                ),
            ],
            1,
        ),
    ],
    ids=["annotated", "second_parameter", "inherited_constructor"],
)
def test_prepare_task_hardcodes_only_the_spied_strategy(
    tmp_path: Path, changes: list[tuple[str, str, str]], mutants: int
) -> None:
    task = _variant(tmp_path, "strategy", changes)

    result = prepare_task(str(task), sandbox="limits")

    assert result["accepted"] is True, result
    [entry] = [e for e in result["errors"] if e["error"] == "hardcoded_strategy"]
    assert entry["status"] == "killed", entry
    assert entry["mutants"] == entry["killed"] == mutants, entry


def test_a_mutant_is_never_killed_by_a_check_the_reference_fails(
    tmp_path: Path,
) -> None:
    """The reference builds a strategy object itself: forbid_runtime_instantiation
    fails on it, so a mutant it fails on proves nothing (review of N5)."""
    task = _variant(
        tmp_path,
        "strategy",
        [
            (
                "pricing.py",
                "from .discounts import Discount",
                "from .discounts import Discount, NoDiscount",
            ),
            (
                "pricing.py",
                "self.discount = discount",
                "self.discount = discount\n        self.spare = NoDiscount()",
            ),
        ],
    )

    result = prepare_task(str(task), sandbox="limits")

    assert result["accepted"] is False
    assert any(
        p.startswith("forbid_runtime_instantiation fails on the reference")
        for p in result["problems"]
    ), result["problems"]
    [entry] = [e for e in result["errors"] if e["error"] == "hardcoded_strategy"]
    assert entry["status"] == "reference_fails", entry
    assert entry["killed"] == 0, entry


_LOOSE_SHAPES = """\
class Shape:
    def area(self) -> float: return 0.0


class Circle:
    def __init__(self, r: float) -> None: self.r = r
    def area(self) -> float: return 3.14 * self.r * self.r


class Square:
    def __init__(self, s: float) -> None: self.s = s
    def area(self) -> float: return self.s * self.s
"""


def test_a_reference_no_operator_can_change_still_runs_its_checks(
    tmp_path: Path,
) -> None:
    """Audit K1: no operator finds anything to change (no class names a base,
    no abstract class, one-line functions), so no mutant is made; the
    unchanged reference is still run, and its failed subclass_of and
    is_abstract_class reject the task instead of an ``accepted: true``."""
    task = tmp_path / "poly0"
    (task / "reference").mkdir(parents=True)
    (task / "reference" / "__init__.py").write_text("", encoding="utf-8")
    (task / "reference" / "shapes.py").write_text(_LOOSE_SHAPES, encoding="utf-8")
    (task / "reference" / "report.py").write_text(
        "def total_area(shapes): return sum(s.area() for s in shapes)\n",
        encoding="utf-8",
    )
    (task / "task.toml").write_text(
        'principle = "polymorphism"\n'
        "[roles]\n"
        'base = ["shapes.Shape"]\n'
        'variant = ["shapes.Circle", "shapes.Square"]\n'
        'client = ["report"]\n'
        "[cases]\n"
        '"report.total_area" = [{ args = [[{ "$new" = "shapes.Circle", '
        'args = [1.0] }, { "$new" = "shapes.Square", args = [2.0] }]] }, '
        "{ args = [[]] }]\n",
        encoding="utf-8",
    )

    result = prepare_task(str(task), sandbox="limits")

    assert result["accepted"] is False, result
    assert result["reference_passes"] is False, result
    assert any(
        p.startswith("subclass_of fails on the reference") for p in result["problems"]
    ), result["problems"]
    assert any(
        p.startswith("is_abstract_class fails on the reference")
        for p in result["problems"]
    ), result["problems"]
    statuses = {e["error"]: e["status"] for e in result["errors"]}
    assert statuses["not_a_subclass"] == "reference_fails", result["errors"]
    assert statuses["concrete_base"] == "reference_fails", result["errors"]


def test_max_mutants_keeps_a_mutant_of_every_error_it_can(tmp_path: Path) -> None:
    """Audit K3: ``max_mutants`` takes the mutants in turn from each error, so
    an error loses all of them only when there are more errors than
    ``max_mutants``; such an error is ``truncated``, never ``no_mutants``
    with a false "found nothing to change"."""
    task = _EXAMPLES / "io_separation"

    two = prepare_task(str(task), max_mutants=2, sandbox="limits")

    assert two["truncated"] is True and two["accepted"] is False, two
    statuses = [e["status"] for e in two["errors"]]
    assert "no_mutants" not in statuses, two["errors"]
    tested = [e for e in two["errors"] if e["status"] != "truncated"]
    assert len(tested) == 2 and all(e["mutants"] == 1 for e in tested), two["errors"]
    for entry in two["errors"]:
        if entry["status"] == "truncated":
            assert "max_mutants" in entry["why"], entry
            assert entry["mutants"] == 0, entry

    every = prepare_task(
        str(task), max_mutants=len(_COVERAGE["io_separation"]), sandbox="limits"
    )
    assert every["truncated"] is True, every
    assert all(e["status"] == "killed" for e in every["errors"]), every["errors"]


def test_a_reference_file_not_in_utf8_is_a_tool_input_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit K5/E5: a reference file in cp1250 (valid Python by its coding
    line) that a step reads as UTF-8 is a tool input error naming the file,
    not a raw UnicodeDecodeError whose text the MCP client never sees. The
    step is stood in for, so the test holds whichever step reads it."""
    from pythonarchtesting.mcp_server.errors import ToolInputError
    from pythonarchtesting.mutation import operators

    task = _variant(tmp_path, "io_separation", [])
    grades = task / "reference" / "grades.py"
    grades.write_bytes(
        (
            "# -*- coding: cp1250 -*-\n# Výpočet známek\n"
            + grades.read_text(encoding="utf-8")
        ).encode("cp1250")
    )

    def read_as_utf8(root: Path, *args: Any, **kwargs: Any) -> list[Any]:
        for path in sorted(Path(root).rglob("*.py")):
            path.read_text(encoding="utf-8")
        return []

    monkeypatch.setattr(operators, "generate_mutants", read_as_utf8)

    with pytest.raises(ToolInputError, match="grades.py") as raised:
        prepare_task(str(task), sandbox="limits")
    assert "UTF-8" in str(raised.value)


def test_file_the_operators_cannot_read_is_named_in_the_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit 2026-11-08 § 2: a reference file the mutation operators cannot
    read gets no mutant. An error that then finds nothing to seed names the
    file instead of a silent not_applicable."""
    from pythonarchtesting.mutation import operators

    task = _variant(tmp_path, "io_separation", [])

    def unreadable(root: Path, *args: Any, **kwargs: Any) -> list[Any]:
        kwargs["skipped"].append(("grades.py", "invalid start byte"))
        return []

    monkeypatch.setattr(operators, "generate_mutants", unreadable)

    result = prepare_task(str(task), sandbox="limits")

    unseeded = [
        e for e in result["errors"] if "the reference contains no" in e.get("why", "")
    ]
    assert unseeded and all(e["status"] == "not_applicable" for e in unseeded)
    assert all("grades.py (invalid start byte)" in e["why"] for e in unseeded)
