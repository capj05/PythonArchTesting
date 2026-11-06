"""Named architectural mutation operators (F4.3)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from pythonarchtesting.mutation.operators import OPERATORS, generate_mutants

_FILES = {
    "__init__.py": '"""Root."""\n',
    "models.py": (
        '"""Models."""\n\nfrom __future__ import annotations\n\n\n'
        "class Order:\n    pass\n"
    ),
    "repository.py": (
        "class Repo:\n"
        "    def save(self, order, *, flush=False):\n"
        "        return order\n\n"
        "    def find(self, key, default=None):\n"
        "        return default\n\n"
        "    def _cache(self):\n"
        "        return {}\n\n\n"
        "def _check(order):\n"
        "    return order\n\n\n"
        "_LIMIT = 3\n"
    ),
    "service.py": (
        "from .models import Order\n\n\n"
        "class Service:\n"
        "    def __init__(self, repo, bus):\n"
        '        """Take the collaborators."""\n'
        "        self._repo = repo\n"
        "        self._bus = bus\n\n"
        "    def place(self, order_id):\n"
        "        order = Order()\n"
        "        self._repo.save(order)\n"
        "        self._bus.publish(\n"
        "            order\n"
        "        )\n"
        "        return order\n"
    ),
    "sub/__init__.py": "",
    "sub/deep.py": "def helper():\n    return 1\n",
}


@pytest.fixture(name="root")
def fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "reference"
    for name, text in _FILES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _by(root: Path, operator: str) -> list:
    return generate_mutants(root, [operator])


def test_operators_are_named() -> None:
    assert OPERATORS == (
        "add_import",
        "lazy_import",
        "add_library",
        "dynamic_import",
        "rebuild_injected",
        "drop_call",
        "use_private_name",
        "break_port",
        "foreign_write",
        "add_io_call",
    )


def test_every_mutant_is_valid_python(root: Path) -> None:
    mutants = generate_mutants(root)

    assert mutants
    for mutant in mutants:
        ast.parse(mutant.source)
    assert len({mutant.id for mutant in mutants}) == len(mutants)


def test_add_import_adds_a_missing_dependency_after_the_header(root: Path) -> None:
    mutants = {m.description: m for m in _by(root, "add_import")}

    mutant = mutants["models imports repository"]
    assert mutant.file == "models.py"
    lines = mutant.source.splitlines()
    assert lines.index("from . import repository") > lines.index(
        "from __future__ import annotations"
    )
    # An existing dependency is no mutant; nothing imports the root package.
    assert "service imports models" not in mutants
    assert not [d for d in mutants if d.endswith("imports __init__")]


def test_add_import_reaches_across_packages_relatively(root: Path) -> None:
    mutants = {m.description: m for m in _by(root, "add_import")}

    assert "from .. import service" in mutants["sub.deep imports service"].source
    assert "from .sub import deep" in mutants["service imports sub.deep"].source


def test_lazy_import_goes_into_the_first_function_after_its_docstring(
    root: Path,
) -> None:
    mutant = next(
        m
        for m in _by(root, "lazy_import")
        if m.description == "service imports repository lazily"
    )

    lines = mutant.source.splitlines()
    index = lines.index("        from . import repository")
    assert lines[index - 1] == '        """Take the collaborators."""'


def test_add_library_imports_the_library_in_every_module(root: Path) -> None:
    mutants = generate_mutants(root, ["add_library"], libraries=["pickle"])

    assert sorted(m.file for m in mutants) == [
        "models.py",
        "repository.py",
        "service.py",
        "sub/__init__.py",
        "sub/deep.py",
    ]
    assert all("import pickle" in m.source for m in mutants)


def test_rebuild_injected_replaces_an_injected_collaborator(root: Path) -> None:
    mutants = _by(root, "rebuild_injected")

    assert [m.description for m in mutants] == [
        "service: Service.__init__ builds its own repo (line 7)",
        "service: Service.__init__ builds its own bus (line 8)",
    ]
    assert "        self._repo = type(repo)()\n" in mutants[0].source


def test_drop_call_removes_a_call_on_a_collaborator(root: Path) -> None:
    mutants = _by(root, "drop_call")

    assert [m.description for m in mutants] == [
        "service: Service.place no longer calls self._repo.save (line 12)",
        "service: Service.place no longer calls self._bus.publish (line 13)",
    ]
    dropped = mutants[1].source
    assert "publish" not in dropped
    assert "        pass\n        return order\n" in dropped


def test_unknown_operator_is_rejected(root: Path) -> None:
    with pytest.raises(ValueError, match="unknown operator"):
        generate_mutants(root, ["swap_everything"])


def test_limit_keeps_the_first_mutants_in_a_stable_order(root: Path) -> None:
    assert generate_mutants(root, limit=3) == generate_mutants(root)[:3]


_ONE_LINERS = {
    "__init__.py": "",
    "models.py": "def one(): return 1\n\n\ndef two():\n    return 2\n",
    "service.py": (
        "class Service:\n"
        "    def __init__(self, repo):\n"
        "        self.repo = repo\n\n"
        "    def place(self, x):\n"
        "        if x: self.repo.save(x)\n"
        "        self.repo.log(x); y = 1\n"
        "        self.repo.flush(\n"
        "            x\n"
        "        )\n"
        "        return y\n\n"
        "    def short(self): self.repo.ping()\n"
    ),
}


def _write_tree(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_one_line_functions_and_compound_statements_yield_only_valid_mutants(
    tmp_path: Path,
) -> None:
    root = _write_tree(tmp_path / "pkg", _ONE_LINERS)

    mutants = generate_mutants(root, ["lazy_import", "drop_call"])

    for mutant in mutants:
        ast.parse(mutant.source)
    drops = [m.description for m in mutants if m.operator == "drop_call"]
    # Only the call on a line of its own is dropped; the others share their
    # line with a header or another statement.
    assert drops == ["service: Service.place no longer calls self.repo.flush (line 8)"]
    lazy = {m.file for m in mutants if m.operator == "lazy_import"}
    # models' first function is a one-liner; the import goes into two().
    assert "models.py" in lazy
    models = next(
        m for m in mutants if m.file == "models.py" and m.operator == "lazy_import"
    )
    assert "def one(): return 1\n" in models.source


def test_use_private_name_adds_a_private_helper_and_calls_it_elsewhere(
    root: Path,
) -> None:
    mutants = {
        (m.file, m.subject): m
        for m in _by(root, "use_private_name")
        if m.file == "service.py"
    }

    mutant = mutants[("service.py", "repository.py")]
    assert mutant.description == "service calls a private helper of repository"
    assert "from .repository import _archtest_private" in mutant.source
    # Called first thing in the first function, after its docstring.
    assert '"""Take the collaborators."""\n        _archtest_private()\n' in (
        mutant.source
    )
    ((file, helper),) = mutant.also
    assert file == "repository.py"
    assert "def _archtest_private():" in helper
    assert helper.startswith(_FILES["repository.py"].rstrip("\n"))


def test_use_private_name_never_targets_the_module_itself(root: Path) -> None:
    assert all(m.file != m.subject for m in _by(root, "use_private_name"))


def test_break_port_adds_a_required_parameter_or_renames_a_public_method(
    root: Path,
) -> None:
    mutants = {m.description: m for m in _by(root, "break_port")}

    added = mutants["repository: Repo.find takes a new required parameter"]
    tree = ast.parse(added.source)
    find = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "find"
    )
    assert [a.arg for a in find.args.args] == ["self", "key", "extra", "default"]
    assert "        return default\n" in added.source
    renamed = mutants["repository: Repo.save is renamed"]
    assert "def save_renamed(self, order, *, flush=False):" in renamed.source
    assert not any("_cache" in description for description in mutants)
    assert not any("__init__" in description for description in mutants)


def test_drop_call_bypasses_a_collaborator_call_inside_an_expression(
    tmp_path: Path,
) -> None:
    root = _write_tree(
        tmp_path / "pkg",
        {
            "__init__.py": "",
            "service.py": (
                "class Service:\n"
                "    def __init__(self, discount, clock):\n"
                "        self._discount = discount\n"
                "        self._clock = clock\n\n"
                "    def place(self, order):\n"
                "        order.total = self._discount.apply(order.total)\n"
                "        return order.stamp(self._clock.now())\n"
            ),
        },
    )

    mutants = _by(root, "drop_call")

    assert [m.description for m in mutants] == [
        "service: Service.place no longer calls self._discount.apply "
        "(line 7, its first argument passed through)",
        "service: Service.place no longer calls self._clock.now (line 8, None instead)",
    ]
    assert "        order.total = order.total\n" in mutants[0].source
    assert "        return order.stamp(None)\n" in mutants[1].source
    for mutant in mutants:
        ast.parse(mutant.source)


def test_dynamic_import_imports_a_library_by_a_computed_name(root: Path) -> None:
    mutants = _by(root, "dynamic_import")

    service = next(m for m in mutants if m.file == "service.py")
    assert service.imported == "pickle"
    assert service.description == (
        "service imports pickle by a computed name in Service.__init__"
    )
    # Inside the first function, after its docstring: run whenever it runs,
    # and no import statement a static rule could see.
    assert (
        '        """Take the collaborators."""\n        __import__("pickle")\n'
        in service.source
    )
    assert "import pickle" not in service.source
    assert {m.file for m in mutants} == {"repository.py", "service.py", "sub/deep.py"}


def test_injection_mutants_name_the_collaborator_and_the_member(root: Path) -> None:
    rebuilt = _by(root, "rebuild_injected")
    dropped = _by(root, "drop_call")

    assert [(m.owner, m.collaborator, m.member) for m in rebuilt] == [
        ("Service", "repo", ""),
        ("Service", "bus", ""),
    ]
    assert [(m.owner, m.collaborator, m.member) for m in dropped] == [
        ("Service", "repo", "save"),
        ("Service", "bus", "publish"),
    ]
    assert [m.line for m in dropped] == [12, 13]


def test_foreign_write_assigns_an_attribute_it_reads_of_another_object(
    tmp_path: Path,
) -> None:
    root = _write_tree(
        tmp_path / "pkg",
        {
            "__init__.py": "",
            "service.py": (
                "class Service:\n"
                "    def place(self, order, prices):\n"
                "        self.count = 1\n"
                "        for price in prices:\n"
                "            order.add(price)\n"
                "        total = order.total\n"
                "        names = {o.key for o in order.lines}\n"
                "        return total, names\n\n"
                "    def peek(self, order): return order.total\n"
            ),
        },
    )

    mutants = _by(root, "foreign_write")

    # Each object read through a name other than self, once per method: a data
    # attribute it reads (not ``add``, which it calls), written right after
    # the statement that calls a method of it for its effect, so under the
    # same condition (inside the loop); a one-line method has no room for it,
    # and a comprehension's variable does not outlive it.
    assert [(m.description, m.line) for m in mutants] == [
        ("service: Service.place writes order.total (line 6)", 6),
    ]
    assert (
        "            order.add(price)\n            order.total = order.total\n"
        in mutants[0].source
    )
    ast.parse(mutants[0].source)


def test_foreign_write_in_a_function_writes_only_to_its_parameters(
    tmp_path: Path,
) -> None:
    root = _write_tree(
        tmp_path / "pkg",
        {
            "__init__.py": "",
            "shop.py": (
                "import os\n\n\n"
                "def sell(inventory, item):\n"
                "    path = os.sep\n"
                "    seen = []\n"
                "    seen.append(item)\n"
                "    size = seen.size\n"
                "    left = inventory.count\n"
                "    return path, size, left\n"
            ),
        },
    )

    mutants = _by(root, "foreign_write")

    # Not ``os`` (imported) nor ``seen`` (its own list): the parameter. With
    # no method call on it, the write follows the first statement reading it.
    assert [(m.description, m.function, m.owner) for m in mutants] == [
        ("shop: sell writes inventory.count (line 10)", "sell", ""),
    ]
    assert "    left = inventory.count\n    inventory.count = inventory.count\n" in (
        mutants[0].source
    )


def test_foreign_write_prefers_a_private_data_attribute_to_a_method(
    tmp_path: Path,
) -> None:
    root = _write_tree(
        tmp_path / "pkg",
        {
            "__init__.py": "",
            "inventory.py": (
                "class Inventory:\n"
                "    def __init__(self, stock):\n"
                "        self._stock = dict(stock)\n"
                "        self.log = []\n\n"
                "    def remove(self, item):\n"
                "        del self._stock[item]\n\n"
                "    def quantity(self, item):\n"
                "        return self._stock.get(item, 0)\n"
            ),
            "shop.py": (
                "from .inventory import Inventory\n\n\n"
                "def sell(inventory: Inventory, item: str) -> None:\n"
                "    inventory.remove(item)\n\n\n"
                "def clear_out(inventory: Inventory, item: str) -> int:\n"
                "    left = inventory.quantity(item)\n"
                "    if left:\n"
                "        inventory.remove(item)\n"
                "    return left\n\n\n"
                "def tally(stock, item):\n"
                "    return stock.quantity(item)\n\n\n"
                "def peek(stock, item):\n"
                "    left = stock.quantity(item)\n"
                "    stock.remove(item)\n"
                "    return left\n"
            ),
        },
    )

    mutants = [m for m in _by(root, "foreign_write") if m.file == "shop.py"]

    # The methods it calls (remove, quantity) are never written. The class the
    # annotation names has the data attributes _stock and log; the private one
    # wins. In clear_out the write goes after the call that changes the state,
    # inside its ``if``. ``tally`` and ``peek`` take an unannotated parameter
    # and read no data attribute of it: nothing to write, no mutant.
    assert [m.description for m in mutants] == [
        "shop: sell writes inventory._stock (line 6)",
        "shop: clear_out writes inventory._stock (line 12)",
    ]
    assert (
        "        inventory.remove(item)\n        inventory._stock = inventory._stock\n"
        in mutants[1].source
    )


def test_add_io_call_talks_to_the_user_first_thing(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path / "pkg",
        {
            "__init__.py": "",
            "grades.py": (
                "def average(grades):\n"
                '    """Mean."""\n'
                "    return sum(grades) / len(grades)\n\n\n"
                "def one(): return 1\n\n\n"
                "class Report:\n"
                "    def show(self):\n"
                "        return 'x'\n"
            ),
        },
    )

    mutants = _by(root, "add_io_call")

    # Every function and method with a body of its own lines, once per call;
    # a one-line function has no room for it.
    assert [(m.function, m.member, m.line) for m in mutants] == [
        ("average", "print", 3),
        ("average", "input", 3),
        ("average", "open", 3),
        ("Report.show", "print", 11),
        ("Report.show", "input", 11),
        ("Report.show", "open", 11),
    ]
    assert '    """Mean."""\n    print("archtest")\n    return' in mutants[0].source
    assert "        input()\n        return 'x'" in mutants[4].source
    assert (
        '    try:\n        open("archtest-missing.txt", encoding="utf-8").close()\n'
        "    except OSError:\n        pass\n    return sum" in mutants[2].source
    )
    for mutant in mutants:
        ast.parse(mutant.source)
