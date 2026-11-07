"""Submissions laid out as beginners lay them out (Review Focus 4).

Each test copies ``err_sell_bypasses_remove`` of the encapsulation principle
into a temporary ``targets_dir`` as ``capj05_capsky`` (a student's package
name, not the reference's), with its test of the stock read through
``quantity()`` so that the bypass is its only violation (the variant also
reads ``_stock``, a ``read_private``), changes it the way a beginner would, runs
``--dynamic`` against the reference and reads the result by the principle:

- no ``__init__.py``, or a sibling module imported absolutely
  (``from inventory import Inventory`` inside the package), or both, must
  not hide the violation in ``sell``;
- a function of the reference the submission renamed is one
  ``missing_required_entity`` finding, not one result per rule, and so is a
  class the cases construct (``$new``) that the submission renamed;
- a file that does not parse is one ``syntax_error`` finding, and it hides
  no violation the tool found in the code it could read;
- a root whose name no package can have (``05capj_capsky``,
  ``capj05-capsky``) is judged as one that can;
- a module of the package named like a standard-library module is not
  aliased: an absolute import of it gets the standard library's module.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable, Optional

import pytest

from pythonarchtesting.cli import main
from pythonarchtesting.mcp_server.reports import class_overview, explain_target

_PRINCIPLE = (
    Path(__file__).resolve().parents[2] / "example" / "principles" / "encapsulation"
)
_STUDENT = "capj05_capsky"
_RELATIVE = "from .inventory import Inventory\n"
_ABSOLUTE = "from inventory import Inventory\n"


def _submit(
    tmp_path: Path,
    change: Callable[[Path], None],
    student: str = _STUDENT,
    reference: Path = _PRINCIPLE,
    mapping: Optional[dict[str, str]] = None,
) -> Path:
    """Copy the variant as the student's package, change it, run the tool."""
    submissions = tmp_path / "submissions"
    package = submissions / student
    shutil.copytree(_PRINCIPLE / "assignments" / "err_sell_bypasses_remove", package)
    _replace(
        package / "shop.py",
        "inventory._stock.get(item, 0) >= quantity",
        "inventory.quantity(item) >= quantity",
    )
    change(package)
    report = tmp_path / "report.json"
    extra: list[str] = []
    if mapping is not None:
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text(json.dumps({"pairs": mapping}), encoding="utf-8")
        extra = ["--mapping", str(mapping_file)]
    main(
        [
            "--source",
            str(reference),
            "--targets-dir",
            str(submissions),
            "--format",
            "json",
            "--output",
            str(report),
            "--dynamic",
            *extra,
        ]
    )
    return report


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _rename_sell(package: Path) -> None:
    """``sell`` renamed, body and parameters kept. A task's role binds ``sell``,
    so the assignment prescribes its name: no pairing by structure."""
    _replace(
        package / "shop.py",
        "def sell(inventory: Inventory, item: str, quantity: int)",
        "def prodej(inventory: Inventory, item: str, quantity: int)",
    )


_HELPER = """

def odeber(inventory: Inventory, item: str, quantity: int) -> None:
    inventory.remove(item, quantity)
"""


def _rename_sell_add_helper(package: Path) -> None:
    """The review's repro: the renamed ``prodej`` keeps the bypass, and a new
    helper ``odeber`` has the one-line body of the reference's ``sell``."""
    _rename_sell(package)
    shop = package / "shop.py"
    shop.write_text(shop.read_text(encoding="utf-8") + _HELPER, encoding="utf-8")


def _no_init(package: Path) -> None:
    (package / "__init__.py").unlink()


def _absolute(package: Path) -> None:
    _replace(package / "shop.py", _RELATIVE, _ABSOLUTE)


def _both(package: Path) -> None:
    _no_init(package)
    _absolute(package)


def _read(
    report: Path, student: str = _STUDENT
) -> tuple[dict[str, Any], dict[str, Any]]:
    overview = class_overview(str(report), "encapsulation")
    explained = explain_target(str(report), student, principle="encapsulation")
    return overview, explained


@pytest.mark.parametrize(
    "change",
    [_no_init, _absolute, _both],
    ids=["no_init_relative", "init_absolute", "no_init_absolute"],
)
def test_the_violation_in_sell_shows_whatever_the_layout(
    tmp_path: Path, change: Callable[[Path], None]
) -> None:
    overview, explained = _read(_submit(tmp_path, change))

    assert (overview["passed"], overview["failed"], overview["not_judged"]) == (0, 1, 0)
    assert list(overview["by_error"]) == ["bypass_method"]
    assert explained["verdict"] == "failed"
    [finding] = explained["findings"]
    assert finding["error_id"] == "bypass_method"
    assert finding["target"] == "shop:sell"
    assert finding["facts"]["class"] == "Inventory"
    assert finding["facts"]["attribute"] == "_stock"


def test_a_renamed_function_is_one_missing_required_entity(tmp_path: Path) -> None:
    def rename(package: Path) -> None:
        _rename_sell(package)

    overview, explained = _read(_submit(tmp_path, rename))

    assert (overview["passed"], overview["failed"], overview["not_judged"]) == (0, 1, 0)
    assert overview["by_error"]["missing_required_entity"]["submissions"] == [_STUDENT]
    assert overview["not_judged_by_reason"] == {}
    assert explained["verdict"] == "failed"
    [finding] = explained["findings"]
    assert finding["error_id"] == "missing_required_entity"
    assert "not_judged" not in finding
    assert finding["facts"]["entity"] == "shop.sell"
    assert finding["facts"]["kind"] == "function"
    assert finding["facts"]["file"] == "shop.py"
    assert finding["facts"]["line"] == 6  # def sell in the reference
    assert "missing_required_entity" in explained["errors"]


def test_a_role_bound_function_is_not_paired_by_structure(tmp_path: Path) -> None:
    """The review's false pass: the reference's one-line ``sell`` must not be
    paired with the student's helper ``odeber`` of the same shape while the
    renamed ``prodej`` keeps the bypass. A role binds ``sell``: it is required
    by name, so it is missing, never passed."""
    overview, explained = _read(_submit(tmp_path, _rename_sell_add_helper))

    assert overview["passed"] == 0
    assert explained["verdict"] == "failed"
    [finding] = explained["findings"]
    assert finding["error_id"] == "missing_required_entity"
    assert finding["facts"]["entity"] == "shop.sell"


def test_a_mapping_pairs_a_role_bound_function_by_its_new_name(
    tmp_path: Path,
) -> None:
    """The way out: ``propose_mapping`` -> ``mapping`` names ``sell -> prodej``,
    and the bypass in ``prodej`` is found."""
    report = _submit(
        tmp_path,
        _rename_sell_add_helper,
        mapping={"shop.sell": "shop.prodej"},
    )
    overview, explained = _read(report)

    assert explained["verdict"] == "failed"
    assert list(overview["by_error"]) == ["bypass_method"]
    [finding] = explained["findings"]
    assert finding["error_id"] == "bypass_method"
    assert finding["target"] == "shop:prodej"


def test_a_syntax_error_is_one_finding_without_a_verdict(tmp_path: Path) -> None:
    def break_it(package: Path) -> None:
        _replace(package / "shop.py", "def report(", "def report(:")

    overview, explained = _read(_submit(tmp_path, break_it))

    assert (overview["passed"], overview["failed"], overview["not_judged"]) == (0, 0, 1)
    assert list(overview["not_judged_by_reason"]) == ["syntax_error"]
    assert explained["verdict"] == "not_judged"
    assert explained["not_judged"] == ["syntax_error"]
    [finding] = explained["findings"]
    assert finding["error_id"] == "syntax_error"
    assert (finding["not_judged"], finding["reason"]) == (True, "syntax_error")
    assert finding["facts"]["file"] == "shop.py"
    assert finding["facts"]["line"] == 25
    assert finding["facts"]["message"]


def test_a_module_named_like_the_standard_library_is_not_aliased(
    tmp_path: Path,
) -> None:
    """``json.py`` in the package, imported absolutely: the probe never puts
    a submission's module in place of a standard-library one, so the import
    gets the standard library's ``json``, which has no ``VALUE``. The probe
    reports that as an import error; it does not break."""

    def shadow(package: Path) -> None:
        (package / "json.py").write_text("VALUE = 1\n", encoding="utf-8")
        _replace(package / "shop.py", _RELATIVE, _ABSOLUTE + "from json import VALUE\n")

    overview, explained = _read(_submit(tmp_path, shadow))

    assert overview["not_judged_by_reason"]["probe_import_error"]["submissions"] == [
        _STUDENT
    ]
    assert explained["verdict"] == "not_judged"
    texts = {finding["text"] for finding in explained["findings"]}
    assert texts and all("cannot import name 'VALUE' from 'json'" in t for t in texts)


@pytest.mark.parametrize("student", ["05capj_capsky", "capj05-capsky"])
def test_a_root_whose_name_no_package_can_have_is_judged_alike(
    tmp_path: Path, student: str
) -> None:
    """Without ``__init__.py`` the static side sees the package the student
    means whatever its name; so does the probe: the violation shows."""
    overview, explained = _read(_submit(tmp_path, _no_init, student), student)

    assert (overview["passed"], overview["failed"], overview["not_judged"]) == (0, 1, 0)
    assert explained["verdict"] == "failed"
    [finding] = explained["findings"]
    assert finding["error_id"] == "bypass_method"
    assert finding["target"] == "shop:sell"


def test_a_syntax_error_does_not_hide_the_violation_found(tmp_path: Path) -> None:
    """A notes file that does not parse leaves ``shop`` readable: its
    violation stays, the submission fails, the syntax error is listed."""

    def notes(package: Path) -> None:
        (package / "poznamky.py").write_text("def x(:\n", encoding="utf-8")

    overview, explained = _read(_submit(tmp_path, notes))

    assert (overview["passed"], overview["failed"], overview["not_judged"]) == (0, 1, 0)
    assert list(overview["by_error"]) == ["bypass_method"]
    assert explained["verdict"] == "failed"
    assert explained["not_judged"] == ["syntax_error"]
    by_id = {finding["error_id"]: finding for finding in explained["findings"]}
    assert set(by_id) == {"bypass_method", "syntax_error"}
    assert by_id["bypass_method"]["target"] == "shop:sell"
    assert by_id["syntax_error"]["facts"]["file"] == "poznamky.py"
    assert by_id["syntax_error"]["facts"]["line"] == 1


def test_a_renamed_class_the_cases_construct_is_one_missing_required_entity(
    tmp_path: Path,
) -> None:
    """``Inventory`` renamed ``Sklad``: every function's cases build an
    ``inventory.Inventory`` (``$new``), which the submission lacks."""

    def rename(package: Path) -> None:
        for path in package.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("Inventory", "Sklad"), encoding="utf-8")

    overview, explained = _read(_submit(tmp_path, rename))

    assert (overview["passed"], overview["failed"], overview["not_judged"]) == (0, 1, 0)
    assert list(overview["by_error"]) == ["missing_required_entity"]
    assert overview["not_judged_by_reason"] == {}
    assert explained["verdict"] == "failed"
    [finding] = explained["findings"]
    assert finding["error_id"] == "missing_required_entity"
    assert "not_judged" not in finding
    assert finding["facts"]["entity"] == "inventory.Inventory"
    assert finding["facts"]["rules"] == ["DYN003/forbid_foreign_writes/v1"]
    assert sorted(finding["facts"]["required_by"]) == [
        "shop:clear_out",
        "shop:report",
        "shop:restock",
        "shop:sell",
    ]


_CASES = '[{"args": [{"$new": "inventory.Inventory", "args": [{"jablko": 5}]}, "jablko", 2]}]'
_TWO_RULES = f"""
    __archtest__: Annotated[  # noqa: F842
        None,
        forbid_foreign_writes(cases={_CASES}),
        forbid_runtime_calls("builtins.print", cases={_CASES}),
    ]
"""
_MARKER_HEADER = """from typing import Annotated

from pythonarchtesting.rules import forbid_foreign_writes, forbid_runtime_calls
"""


def test_two_rules_on_one_missing_entity_give_one_finding(tmp_path: Path) -> None:
    """A reference (with markers, not a task) whose ``sell`` two markers check;
    the submission has no ``sell``: one ``missing_required_entity`` finding
    naming both rules."""
    reference = tmp_path / "reference"
    shutil.copytree(_PRINCIPLE / "reference", reference)
    shop = reference / "shop.py"
    _replace(shop, _RELATIVE, _RELATIVE + _MARKER_HEADER)
    _replace(
        shop,
        "-> None:\n    inventory.remove(",
        "-> None:" + _TWO_RULES + "    inventory.remove(",
    )

    def rename(package: Path) -> None:
        _rename_sell(package)

    overview, explained = _read(_submit(tmp_path, rename, reference=reference))

    assert explained["verdict"] == "failed"
    [finding] = explained["findings"]
    assert finding["error_id"] == "missing_required_entity"
    assert finding["facts"]["entity"] == "shop.sell"
    assert sorted(finding["facts"]["rules"]) == [
        "DYN001/forbid_runtime_calls/v1",
        "DYN003/forbid_foreign_writes/v1",
    ]
