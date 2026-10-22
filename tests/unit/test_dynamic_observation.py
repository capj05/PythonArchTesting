"""Tests for what the probe observes while target code runs.

Covers the attribute writes behind ``forbid_foreign_writes``, the project calls
behind runtime ``enforce_flow`` and the imports behind
``forbid_runtime_imports``, each through a real child interpreter.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from pythonarchtesting.dynamic.runner import run_cases, run_import_check


def _write_package(root: Path, files: dict[str, str]) -> Path:
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    for name, source in files.items():
        (root / name).write_text(textwrap.dedent(source), encoding="utf-8")
    return root


def _cases(
    root: Path,
    qualname: str,
    cases: list,
    kind: str = "function",
    module_path: str = "ledger",
    observe: dict | None = None,
):
    outcome = run_cases(
        target_root=root,
        module_path=module_path,
        qualname=qualname,
        kind=kind,
        cases=cases,
        init=None,
        timeout_s=10,
        observe=observe,
    )
    assert outcome.status == "completed", (outcome.error, outcome.stderr)
    return outcome.cases


# --- attribute writes ------------------------------------------------------

_ACCOUNT = """
from dataclasses import dataclass


class Base:
    def _set_owner(self, owner):
        self.owner = owner


class Account(Base):
    def __init__(self, owner, balance=0.0):
        self._set_owner(owner)
        self.balance = balance

    def deposit(self, amount):
        self.balance += amount

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, value):
        self._label = value

    @classmethod
    def opened(cls, owner):
        account = cls(owner)
        account.balance = 1.0
        return account

    @staticmethod
    def reset(account):
        account.balance = 0.0

    def later(self):
        (lambda: setattr(self, "balance", 5.0))()


@dataclass
class Entry:
    amount: float
    note: str = ""
"""

_UTIL = """
def touch(account):
    account.balance = -1.0
"""

_BANK = """
from types import SimpleNamespace

from . import util
from .account import Account, Entry


def direct(account):
    account.balance = 99.0


def _helper(account):
    account.balance = 1.0


def via_helper(account):
    _helper(account)
    _helper(account)


def via_other_module(account):
    util.touch(account)


def twice(account):
    account.balance = 1.0
    account.balance = 2.0


def polite(account):
    account.deposit(5.0)
    account.label = "main"
    Account.reset(account)
    account.later()
    return Account.opened("bob")


def make_entry():
    return Entry(1.0)


def edit_entry():
    entry = Entry(1.0)
    entry.note = "edited"
    return entry


def outside():
    namespace = SimpleNamespace()
    namespace.value = 1
    return namespace


class Teller:
    def __init__(self, account):
        self.account = account

    def pay(self, amount):
        self.account.deposit(amount)

    def cheat(self):
        self.account.balance = 0.0
"""

_ACCOUNT_ARG = {"$new": "account.Account", "args": ["ada", 10.0]}


@pytest.fixture
def bank_root(tmp_path: Path) -> Path:
    return _write_package(
        tmp_path / "bank_pkg",
        {"account.py": _ACCOUNT, "util.py": _UTIL, "bank.py": _BANK},
    )


def _writes(root: Path, qualname: str, cases: list, kind: str = "function"):
    return _cases(
        root,
        qualname,
        cases,
        kind=kind,
        module_path="bank",
        observe={"writes": True},
    )


def _line(source: str, fragment: str) -> int:
    lines = textwrap.dedent(source).splitlines()
    return next(no for no, line in enumerate(lines, 1) if fragment in line)


def test_a_write_from_a_plain_function_is_foreign(bank_root: Path) -> None:
    cases = _writes(bank_root, "direct", [{"args": [_ACCOUNT_ARG]}])

    assert cases[0]["status"] == "passed"
    assert cases[0]["writes"] == [
        {
            "class": "Account",
            "attribute": "balance",
            "writer": "bank:direct",
            "file": "bank.py",
            "line": _line(_BANK, "account.balance = 99.0"),
            "change": "assigned",
        }
    ]


def test_a_write_from_a_module_level_helper_is_foreign(bank_root: Path) -> None:
    same = _writes(bank_root, "via_helper", [{"args": [_ACCOUNT_ARG]}])
    other = _writes(bank_root, "via_other_module", [{"args": [_ACCOUNT_ARG]}])

    # The helper runs twice from one line; the write is reported once.
    assert [w["writer"] for w in same[0]["writes"]] == ["bank:_helper"]
    assert [(w["writer"], w["file"]) for w in other[0]["writes"]] == [
        ("util:touch", "util.py")
    ]


def test_writes_from_different_lines_are_reported_separately(bank_root: Path) -> None:
    cases = _writes(bank_root, "twice", [{"args": [_ACCOUNT_ARG]}])

    second = _line(_BANK, "account.balance = 2.0")
    assert [w["line"] for w in cases[0]["writes"]] == [second - 1, second]


def test_writes_are_reset_between_cases(bank_root: Path) -> None:
    cases = _writes(
        bank_root, "via_helper", [{"args": [_ACCOUNT_ARG]}, {"args": [_ACCOUNT_ARG]}]
    )

    assert [len(case["writes"]) for case in cases] == [1, 1]


def test_writes_by_the_class_itself_are_not_foreign(bank_root: Path) -> None:
    # deposit, a property setter, a static method, a class method and
    # inherited Base._set_owner via __init__ all belong to Account.
    cases = _writes(bank_root, "polite", [{"args": [_ACCOUNT_ARG]}])

    writers = [w["writer"] for w in cases[0]["writes"]]
    # Only the lambda nested in Account.later is outside the class's methods.
    assert writers == ["account:Account.later.<locals>.<lambda>"]


def test_dataclass_generated_init_is_not_foreign(bank_root: Path) -> None:
    built = _writes(bank_root, "make_entry", [{}])
    edited = _writes(bank_root, "edit_entry", [{}])

    assert built[0]["writes"] == []
    assert [(w["class"], w["attribute"]) for w in edited[0]["writes"]] == [
        ("Entry", "note")
    ]


def test_objects_of_classes_outside_the_target_are_ignored(bank_root: Path) -> None:
    cases = _writes(bank_root, "outside", [{}])

    assert cases[0]["writes"] == []


def test_a_method_of_another_class_writing_is_foreign(bank_root: Path) -> None:
    init = {"args": [_ACCOUNT_ARG]}
    pay = _writes(bank_root, "Teller.pay", [{"init": init, "args": [1.0]}], "method")
    cheat = _writes(bank_root, "Teller.cheat", [{"init": init}], "method")

    # Teller.__init__ sets its own attribute before recording starts anyway.
    assert pay[0]["writes"] == []
    assert [w["writer"] for w in cheat[0]["writes"]] == ["bank:Teller.cheat"]


def test_writes_are_only_reported_when_observed(bank_root: Path) -> None:
    cases = _cases(
        bank_root,
        "direct",
        [{"args": [_ACCOUNT_ARG]}],
        module_path="bank",
        observe={"calls": True},
    )

    assert "writes" not in cases[0]


# --- project calls used by runtime enforce_flow -----------------------------

_STEPS = """
def parse(line):
    return line.split(";")


def validate(fields):
    return _require(fields)


def _require(fields):
    if not fields:
        raise ValueError("empty")
    return fields
"""

_LEDGER = """
import json
import sys

from . import steps


def ingest(line):
    record = line
    record = steps.parse(record)
    if record:
        record = steps.validate(record)
    return json.dumps(record)


def batch(lines):
    out = []
    for line in lines:
        out.append(steps.parse(line))
    return out


def explode(line):
    steps.parse(line)
    raise ValueError("boom")


def counter():
    yield steps.parse("a")


def untraceable():
    sys.settrace(None)
    return steps.parse("a")


class Holder:
    def __init__(self, sep):
        self.sep = sep

    def apply_all(self, line):
        fields = steps.parse(line + self.sep)
        return steps.validate(fields)
"""


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return _write_package(
        tmp_path / "ledger_pkg", {"ledger.py": _LEDGER, "steps.py": _STEPS}
    )


def _span(stage: str, first: str, last: str | None = None) -> dict:
    return {
        "stage": stage,
        "start": _line(_LEDGER, first),
        "end": _line(_LEDGER, last or first),
        "variable": "record",
    }


def _steps(*qualnames: str) -> list[dict]:
    return [{"module": "steps", "qualname": name} for name in qualnames]


def _flow(root: Path, qualname: str, case: dict, kind: str = "function") -> dict:
    return _cases(root, qualname, [case], kind=kind)[0]


def test_reference_stages_record_their_direct_project_calls(root: Path) -> None:
    spans = [
        _span("received", "record = line"),
        _span("parsed", "record = steps.parse(record)"),
        _span("checked", "if record:", "record = steps.validate(record)"),
    ]
    case = _flow(root, "ingest", {"args": ["a;b"], "capture_stages": {"spans": spans}})

    assert case["status"] == "passed", case["failures"]
    # validate's own call of _require is not direct; json.dumps is stdlib.
    assert case["stages"] == [
        ["received", []],
        ["parsed", _steps("parse")],
        ["checked", _steps("validate")],
    ]
    assert "flow_calls" not in case


def test_a_stage_in_a_loop_is_recorded_each_time(root: Path) -> None:
    spans = [_span("parsed", "out.append(steps.parse(line))")]
    case = _flow(
        root, "batch", {"args": [["a", "b"]], "capture_stages": {"spans": spans}}
    )

    assert case["stages"] == [["parsed", _steps("parse")], ["parsed", _steps("parse")]]


def test_target_calls_cover_every_depth_in_order(root: Path) -> None:
    case = _flow(root, "ingest", {"args": ["a;b"], "flow_calls": True})

    assert case["status"] == "passed", case["failures"]
    assert case["flow_calls"] == _steps("parse", "validate", "_require")
    assert "stages" not in case


def test_a_method_is_traced_on_an_instance_built_from_init(root: Path) -> None:
    case = _flow(
        root,
        "Holder.apply_all",
        {"init": {"args": [";"]}, "args": ["a"], "flow_calls": True},
        kind="method",
    )

    assert case["status"] == "passed", case["failures"]
    assert case["flow_calls"] == _steps("parse", "validate", "_require")


def test_a_raise_fails_the_reference_but_not_the_target(root: Path) -> None:
    spans = [_span("parsed", "steps.parse(line)")]
    reference = _flow(
        root, "explode", {"args": ["a"], "capture_stages": {"spans": spans}}
    )
    target = _flow(root, "explode", {"args": ["a"], "flow_calls": True})

    # The reference has to finish to say what its stages are.
    assert reference["status"] == "failed"
    assert reference["failures"][0] == "unexpected ValueError: boom"
    assert target["status"] == "passed"
    assert target["raised"] == "ValueError: boom"
    assert target["flow_calls"] == _steps("parse")


def test_tracing_a_generator_is_a_setup_error(root: Path) -> None:
    case = _flow(root, "counter", {"flow_calls": True})

    assert case["status"] == "error"
    assert "generators or coroutines" in case["failures"][0]


def test_a_target_that_clears_the_tracer_is_a_setup_error(root: Path) -> None:
    case = _flow(root, "untraceable", {"flow_calls": True})

    assert case["status"] == "error"
    assert "replaced the trace function" in case["failures"][0]


# --- imports ---------------------------------------------------------------

_IMPORTS = {
    "helpers.py": "import decimal\n",
    "ledger.py": """
        import json

        from . import helpers
        """,
    "lazy.py": """
        import importlib

        driver = importlib.import_module("sqlite3")
        other = __import__("csv")
        """,
    "low.py": """
        import importlib

        importlib.__import__("sqlite3")
        """,
    "from_import.py": """
        from xml.sax import saxutils
        """,
}


@pytest.fixture
def imports_root(tmp_path: Path) -> Path:
    return _write_package(tmp_path / "imports_pkg", _IMPORTS)


def _imports(root: Path, module_path: str, forbidden: list, allow: list) -> list:
    outcome = run_import_check(
        target_root=root,
        module_path=module_path,
        forbidden=forbidden,
        allow=allow,
        timeout_s=10,
    )
    assert outcome.status == "completed", outcome.error
    return outcome.imports


def test_import_check_attributes_imports_to_target_files_only(
    imports_root: Path,
) -> None:
    hits = _imports(imports_root, "ledger", ["decimal", "re", "sqlite3"], [])

    # json imports re internally, but that is the standard library's import.
    assert [(hit["module"], hit["file"]) for hit in hits] == [("decimal", "helpers.py")]


def test_import_check_honours_the_allow_list(imports_root: Path) -> None:
    hits = _imports(imports_root, "lazy", ["importlib", "csv"], ["importlib"])

    assert [hit["module"] for hit in hits] == ["csv"]


def test_import_check_resolves_relative_imports(imports_root: Path) -> None:
    hits = _imports(imports_root, "ledger", ["imports_pkg.helpers"], [])

    assert [hit["module"] for hit in hits] == ["imports_pkg.helpers"]


def test_import_check_sees_string_based_imports(imports_root: Path) -> None:
    hits = _imports(imports_root, "lazy", ["sqlite3", "csv"], [])

    assert {(hit["module"], hit["phase"]) for hit in hits} == {
        ("sqlite3", "import"),
        ("csv", "import"),
    }


def test_importlib_dunder_import_is_recorded(imports_root: Path) -> None:
    hits = _imports(imports_root, "low", ["sqlite3"], [])

    assert [hit["module"] for hit in hits] == ["sqlite3"]


def test_from_import_of_an_allowed_submodule_does_not_flag_the_parent(
    imports_root: Path,
) -> None:
    assert _imports(imports_root, "from_import", ["xml"], ["xml.sax.saxutils"]) == []
    assert _imports(imports_root, "from_import", ["xml.dom"], []) == []
