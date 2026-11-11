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
        "mutate_private_container",
        "mutate_public_container",
        "stub_role_call",
        "add_io_via_helper",
        "read_private_attribute",
        "add_builtin_call",
        "drop_base",
        "concretize_base",
        "hardcode_collaborator",
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
            "order.py": (
                "class Order:\n"
                "    def __init__(self):\n"
                "        self.total = 0\n"
                "        self.lines = []\n\n"
                "    def add(self, price):\n"
                "        self.total += price\n"
            ),
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

    mutants = [m for m in _by(root, "foreign_write") if m.file == "service.py"]

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
            "stock.py": (
                "class Stock:\n" "    def __init__(self):\n" "        self.count = 0\n"
            ),
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

    mutants = [m for m in _by(root, "foreign_write") if m.file == "shop.py"]

    # Not ``os`` (imported) nor ``seen`` (its own list): the parameter, a
    # ``Stock`` by the data attribute it reads. With no method call on it,
    # the write follows the first statement reading it.
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
    # the methods called on it make an ``Inventory``; ``tally`` only returns
    # their result, which leaves no simple statement to follow.
    assert [m.description for m in mutants] == [
        "shop: sell writes inventory._stock (line 6)",
        "shop: clear_out writes inventory._stock (line 12)",
        "shop: peek writes stock._stock (line 22)",
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


def _inserted(original: str, mutant: str) -> list[str]:
    """The lines ``mutant`` adds to ``original``; it must remove none."""
    import difflib

    diff = list(difflib.ndiff(original.splitlines(), mutant.splitlines()))
    assert not [line for line in diff if line.startswith("- ")], diff
    return [line[2:] for line in diff if line.startswith("+ ")]


_CONTAINERS = {
    "__init__.py": "",
    "store.py": (
        "class Box:\n"
        "    def __init__(self):\n"
        "        self._items = {}\n"
        "        self.name = 'box'\n\n"
        "    def put(self, key, value):\n"
        "        self._items[key] = value\n\n\n"
        "class Bag:\n"
        "    def __init__(self, things=None):\n"
        "        self._things: list[str] = list(things or [])\n"
        "        self.tags = []\n\n"
        "    def add(self, thing):\n"
        "        self._things.append(thing)\n\n"
        "    def tags_of(self, other: 'Bag'):\n"
        "        other.add('x')\n"
        "        return other.tags\n\n\n"
        "class Pot:\n"
        "    def __init__(self):\n"
        "        self._shape = ()\n"
        "        self._seen = set()\n\n"
        "    def mark(self, item):\n"
        "        self._seen.add(item)\n"
    ),
    "client.py": (
        "from .store import Bag, Box\n\n\n"
        "def fill(box: Box):\n"
        "    box.put('a', 1)\n"
        "    return box\n\n\n"
        "def pack(bag: Bag, extra):\n"
        "    size = len(extra)\n"
        "    bag.add('x')\n"
        "    return size\n\n\n"
        "def visit(pot):\n"
        "    pot.mark(1)\n\n\n"
        "def tally(seen: set[int]):\n"
        "    seen.add(1)\n"
    ),
}


def test_mutate_private_container_dict_list_set(tmp_path: Path) -> None:
    root = _write_tree(tmp_path / "pkg", _CONTAINERS)
    original = (root / "client.py").read_text(encoding="utf-8")

    mutants = _by(root, "mutate_private_container")

    # One per client function and object, right after the first statement
    # that calls a method of it; the class of an unannotated parameter is the
    # one project class with the methods called on it, and an annotated
    # parameter of no project class is none (``seen: set[int]``, though Bag
    # has an ``add``). A tuple is no container; a method of the class itself
    # is no client.
    assert [(m.file, m.function, m.owner, m.member, m.line) for m in mutants] == [
        ("client.py", "fill", "Box", "_items", 6),
        ("client.py", "pack", "Bag", "_things", 12),
        ("client.py", "visit", "Pot", "_seen", 17),
    ]
    assert [_inserted(original, m.source) for m in mutants] == [
        ['    box._items["__archtest__"] = 0'],
        ["    bag._things.append(0)"],
        ["    pot._seen.add(0)"],
    ]
    for mutant in mutants:
        ast.parse(mutant.source)
    assert generate_mutants(root, ["mutate_private_container"]) == mutants


def test_mutate_public_container_skips_private_and_methods(tmp_path: Path) -> None:
    root = _write_tree(tmp_path / "pkg", _CONTAINERS)
    original = (root / "client.py").read_text(encoding="utf-8")

    mutants = _by(root, "mutate_public_container")

    # Only Bag has a public container (``tags``): Box's ``name`` is a string,
    # Pot's containers are private, and a method (``add``) is never one.
    assert [(m.function, m.owner, m.member) for m in mutants] == [
        ("pack", "Bag", "tags")
    ]
    assert _inserted(original, mutants[0].source) == ["    bag.tags.append(0)"]
    ast.parse(mutants[0].source)


def test_stub_role_call_replaces_only_logic_calls(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path / "pkg",
        {
            "__init__.py": "",
            "grades.py": (
                "def parse(text):\n    return [int(w) for w in text.split()]\n\n\n"
                "def average(grades):\n    return sum(grades) / len(grades)\n\n\n"
                "class Report:\n    pass\n"
            ),
            "tools.py": "def size(items):\n    return len(items)\n",
            "app.py": (
                "from . import tools\n"
                "from .grades import Report, average, parse\n\n\n"
                "def main():\n"
                "    text = input('> ')\n"
                "    grades = parse(text)\n"
                "    print(average(parse(text)), tools.size(grades), Report())\n"
                "    print(len(grades))\n"
            ),
        },
    )

    mutants = [m for m in _by(root, "stub_role_call") if m.file == "app.py"]

    # One mutant per module the function calls functions of (``member``);
    # print, input, len and a class are left alone.
    stub = "(lambda *a, **k: None)"
    assert [(m.function, m.member, m.line) for m in mutants] == [
        ("main", "grades", 7),
        ("main", "tools", 8),
    ]
    by_member = {m.member: m.source.splitlines() for m in mutants}
    assert by_member["grades"][5:9] == [
        "    text = input('> ')",
        f"    grades = {stub}(text)",
        f"    print({stub}({stub}(text)), tools.size(grades), Report())",
        "    print(len(grades))",
    ]
    assert by_member["tools"][7] == (
        f"    print(average(parse(text)), {stub}(grades), Report())"
    )
    for mutant in mutants:
        ast.parse(mutant.source)


def test_add_io_via_helper_creates_helper_module_and_call(tmp_path: Path) -> None:
    files = {
        "grades.py": (
            "def average(grades):\n"
            '    """Mean."""\n'
            "    return sum(grades) / len(grades)\n\n\n"
            "def one(): return 1\n"
        )
    }
    package = _write_tree(tmp_path / "pkg", {"__init__.py": "", **files})
    flat = _write_tree(tmp_path / "flat", files)
    original = files["grades.py"]

    mutants = _by(package, "add_io_via_helper")

    # A new helper module that prints, and one line in each function with a
    # body of its own lines that imports and calls it first thing; a module
    # of a package imports it relatively, a top-level module absolutely.
    helper = "def say(*args):\n    print(*args)\n"
    assert [(m.file, m.function, m.member, m.line) for m in mutants] == [
        ("grades.py", "average", "print", 3)
    ]
    (mutant,) = mutants
    assert mutant.also == (("_archtest_helper.py", helper),)
    assert _inserted(original, mutant.source) == [
        '    from ._archtest_helper import say; say("archtest")'
    ]
    ast.parse(mutant.source)
    assert _by(package, "add_io_via_helper") == mutants
    (absolute,) = _by(flat, "add_io_via_helper")
    assert _inserted(original, absolute.source) == [
        '    from _archtest_helper import say; say("archtest")'
    ]


_READS = {
    "__init__.py": "",
    "store.py": (
        "class Box:\n"
        "    def __init__(self):\n"
        "        self._items = {}\n"
        "        self.__secret = 1\n"
        "        self.name = 'box'\n\n"
        "    def size(self):\n"
        "        return len(self._items)\n\n"
        "    def merge(self, other: 'Box'):\n"
        "        return self.size() + other.size()\n\n\n"
        "class Tag:\n"
        "    def __init__(self):\n"
        "        self.__code = 'x'\n\n"
        "    def code(self):\n"
        "        return self.__code\n"
    ),
    "client.py": (
        "from .store import Box, Tag\n\n\n"
        "def count(box: Box) -> int:\n"
        '    """Count."""\n'
        "    return box.size()\n\n\n"
        "def label(tag: Tag):\n"
        "    return tag.code()\n\n\n"
        "def plain(items: dict):\n"
        "    return items.items()\n\n\n"
        "def busy(box: Box):\n"
        "    for _ in range(2):\n"
        "        box.size()\n"
    ),
}


def test_read_private_attribute_operator(tmp_path: Path) -> None:
    root = _write_tree(tmp_path / "pkg", _READS)
    original = (root / "client.py").read_text(encoding="utf-8")

    mutants = _by(root, "read_private_attribute")

    # A client function reads the first private data attribute of an object
    # of a project class it got as a parameter, first thing (after the
    # docstring). A name-mangled attribute is read as a student outside the
    # class must spell it (``tag._Tag__code``); a method of the class itself
    # is no client (``Box.merge``), a parameter of no project class gives
    # nothing (``items: dict``), nor does a function that uses ``_`` itself.
    assert [(m.file, m.function, m.owner, m.member, m.line) for m in mutants] == [
        ("client.py", "count", "Box", "_items", 6),
        ("client.py", "label", "Tag", "_Tag__code", 10),
    ]
    assert [_inserted(original, m.source) for m in mutants] == [
        ["    _ = box._items"],
        ["    _ = tag._Tag__code"],
    ]
    for mutant in mutants:
        ast.parse(mutant.source)
    assert generate_mutants(root, ["read_private_attribute"]) == mutants


def test_read_private_attribute_sees_attributes_a_tuple_assigns(
    tmp_path: Path,
) -> None:
    """``self._x, self._y = x, y`` assigns two data attributes: the operator
    reads the first."""
    files = {
        "__init__.py": "",
        "point.py": (
            "class Point:\n"
            "    def __init__(self, x, y):\n"
            "        self._x, self._y = x, y\n\n"
            "    def x(self):\n"
            "        return self._x\n"
        ),
        "client.py": (
            "from .point import Point\n\n\n"
            "def show(p: Point):\n"
            "    return p.x()\n"
        ),
    }
    root = _write_tree(tmp_path / "pkg", files)

    mutants = _by(root, "read_private_attribute")

    assert [(m.function, m.owner, m.member) for m in mutants] == [
        ("show", "Point", "_x")
    ]


_WIDE = {
    "__init__.py": "",
    "store.py": (
        "from collections import Counter, OrderedDict, defaultdict\n"
        "from dataclasses import dataclass, field\n\n\n"
        "class A:\n"
        "    def __init__(self, items=None):\n"
        "        self._items = items if items is not None else {}\n\n"
        "    def get(self):\n        return self._items\n\n\n"
        "class B:\n"
        "    def __init__(self, items=None):\n"
        "        self._items = items or []\n\n"
        "    def get(self):\n        return self._items\n\n\n"
        "class C:\n"
        "    def __init__(self):\n"
        "        self._counts = defaultdict(int)\n\n"
        "    def get(self):\n        return self._counts\n\n\n"
        "class D:\n"
        "    def __init__(self):\n"
        "        self._seen = {x for x in ()}\n\n"
        "    def get(self):\n        return self._seen\n\n\n"
        "@dataclass\n"
        "class E:\n"
        "    _rows: list = field(default_factory=list)\n\n"
        "    def get(self):\n        return self._rows\n\n\n"
        "class F:\n"
        "    def __init__(self):\n"
        "        self._maybe = [] if self else None\n"
        "        self._reset = []\n\n"
        "    def get(self):\n        return self._maybe\n\n"
        "    def reset(self):\n        self._reset = None\n\n\n"
        "class G:\n"
        "    def __init__(self):\n"
        "        self.__hidden = Counter()\n"
        "        self._order = OrderedDict()\n\n"
        "    def get(self):\n        return self.__hidden\n"
    ),
    "client.py": (
        "from .store import A, B, C, D, E, F, G\n\n\n"
        "def a(x: A):\n    x.get()\n\n\n"
        "def b(x: B):\n    x.get()\n\n\n"
        "def c(x: C):\n    x.get()\n\n\n"
        "def d(x: D):\n    x.get()\n\n\n"
        "def e(x: E):\n    x.get()\n\n\n"
        "def f(x: F):\n    x.get()\n\n\n"
        "def g(x: G):\n    x.get()\n"
    ),
}


def test_mutate_private_container_recognises_more_containers(tmp_path: Path) -> None:
    """A choice with a container branch, ``defaultdict``/``Counter``/
    ``OrderedDict``, a comprehension and a dataclass field's default factory
    build containers; ``[] if ... else None`` may leave none, and a container
    another method sets to ``None`` (F's ``_reset``) is none either. A
    name-mangled ``__hidden`` is written as code outside G must: ``_G__hidden``."""
    root = _write_tree(tmp_path / "pkg", _WIDE)
    original = (root / "client.py").read_text(encoding="utf-8")

    mutants = _by(root, "mutate_private_container")

    assert [(m.function, m.owner, m.member) for m in mutants] == [
        ("a", "A", "_items"),
        ("b", "B", "_items"),
        ("c", "C", "_counts"),
        ("d", "D", "_seen"),
        ("e", "E", "_rows"),
        ("g", "G", "_G__hidden"),
    ]
    assert [_inserted(original, m.source) for m in mutants] == [
        ['    x._items["__archtest__"] = 0'],
        ["    x._items.append(0)"],
        ['    x._counts["__archtest__"] = 0'],
        ["    x._seen.add(0)"],
        ["    x._rows.append(0)"],
        ['    x._G__hidden["__archtest__"] = 0'],
    ]


_UNANNOTATED = {
    "__init__.py": "",
    "store.py": (
        "class Store:\n"
        "    def __init__(self):\n"
        "        self._items = {}\n\n"
        "    def items(self):\n        return dict(self._items)\n\n"
        "    def take(self, key):\n        return self._items.pop(key)\n"
    ),
    "client.py": (
        "def listing(pairs):\n"
        "    pairs.items()\n"
        "    return pairs\n\n\n"
        "def grab(store, key):\n"
        "    store.take(key)\n"
        "    return key\n"
    ),
}


def test_an_unannotated_parameter_is_no_guessed_project_object(tmp_path: Path) -> None:
    """Without the task's cases, a parameter on which only methods a builtin
    container has too are called (``pairs.items()``) is not taken for a
    ``Store``; one on which ``take`` is called is. With them, the class the
    cases build decides, and a parameter they build nothing for is none."""
    root = _write_tree(tmp_path / "pkg", _UNANNOTATED)

    guessed = _by(root, "mutate_private_container")
    hinted = generate_mutants(
        root,
        ["mutate_private_container"],
        parameter_classes={
            ("client.py", "listing"): {"pairs": "Store"},
            ("client.py", "grab"): {},
        },
    )

    assert [(m.function, m.owner) for m in guessed] == [("grab", "Store")]
    assert [(m.function, m.owner) for m in hinted] == [("listing", "Store")]


def test_foreign_write_writes_a_mangled_attribute_as_outside_code_must(
    tmp_path: Path,
) -> None:
    root = _write_tree(
        tmp_path / "pkg",
        {
            "__init__.py": "",
            "store.py": (
                "class Store:\n"
                "    def __init__(self):\n"
                "        self.__items = {}\n\n"
                "    def size(self):\n        return len(self.__items)\n"
            ),
            "client.py": (
                "from .store import Store\n\n\n"
                "def count(store: Store):\n"
                "    store.size()\n"
                "    return 1\n"
            ),
        },
    )
    original = (root / "client.py").read_text(encoding="utf-8")

    [mutant] = _by(root, "foreign_write")

    assert _inserted(original, mutant.source) == [
        "    store._Store__items = store._Store__items"
    ]


def test_stub_role_call_follows_a_star_import(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path / "pkg",
        {
            "__init__.py": "",
            "grades.py": (
                "def parse(text):\n    return text.split()\n\n\n"
                "def _hidden():\n    return 0\n"
            ),
            "app.py": (
                "from .grades import *\n\n\n"
                "def main():\n"
                "    words = parse(input())\n"
                "    print(words)\n"
            ),
        },
    )

    [mutant] = _by(root, "stub_role_call")

    assert (mutant.function, mutant.member) == ("main", "grades")
    assert "(lambda *a, **k: None)(input())" in mutant.source


_KINDS = {
    "__init__.py": "",
    "kinds.py": (
        "from abc import ABC, abstractmethod\n"
        "import abc\n\n\n"
        "class Base(ABC):\n"
        "    @abstractmethod\n"
        "    def size(self) -> float:\n"
        "        raise NotImplementedError\n\n"
        "    @abc.abstractmethod\n"
        "    def name(self) -> str: ...\n\n"
        "    def twice(self) -> float:\n"
        "        return 2 * self.size()\n\n\n"
        "class Meta(metaclass=abc.ABCMeta):\n"
        "    @abstractmethod\n"
        "    def run(self): ...\n\n\n"
        "class One(Base):\n"
        "    def size(self) -> float:\n"
        "        return 1.0\n\n"
        "    def name(self) -> str:\n"
        "        return 'one'\n\n\n"
        "class Two(One, Meta, metaclass=abc.ABCMeta):\n"
        "    def run(self):\n"
        "        return 2\n\n\n"
        "class Plain(object):\n"
        "    pass\n"
    ),
    "client.py": (
        "def total(items):\n"
        "    return sum(item.size() for item in items)\n\n\n"
        "def short(items): return items\n"
    ),
}


def test_add_builtin_call_seeds_any_builtin_call_first_thing(tmp_path: Path) -> None:
    root = _write_tree(tmp_path / "pkg", dict(_KINDS))

    mutants = [m for m in _by(root, "add_builtin_call") if m.file == "client.py"]

    # The I/O calls of add_io_call, and a type check: isinstance() and type();
    # a one-line function has no room for them.
    assert [(m.function, m.member, m.line) for m in mutants] == [
        ("total", "print", 2),
        ("total", "input", 2),
        ("total", "open", 2),
        ("total", "isinstance", 2),
        ("total", "type", 2),
    ]
    # Each a real type test, as forbid_runtime_calls counts one: a class
    # computed at run time, a result of type() that is compared.
    assert "    isinstance(None, (object,)[0])\n    return sum" in mutants[3].source
    assert "    type((None,)[0]) == object\n    return sum" in mutants[4].source
    for mutant in mutants:
        ast.parse(mutant.source)


def test_add_io_call_is_add_builtin_call_restricted_to_input_and_output(
    tmp_path: Path,
) -> None:
    root = _write_tree(tmp_path / "pkg", dict(_KINDS))

    io = _by(root, "add_io_call")
    builtin = [
        m
        for m in _by(root, "add_builtin_call")
        if m.member in ("print", "input", "open")
    ]

    assert [(m.file, m.function, m.member, m.source) for m in io] == [
        (m.file, m.function, m.member, m.source) for m in builtin
    ]


def test_drop_base_removes_one_base_of_a_class(tmp_path: Path) -> None:
    root = _write_tree(tmp_path / "pkg", dict(_KINDS))
    original = (root / "kinds.py").read_text(encoding="utf-8")

    mutants = _by(root, "drop_base")

    # One mutant per class and base; `object` and keywords stay.
    assert [(m.function, m.member, m.line) for m in mutants] == [
        ("Base", "ABC", 5),
        ("One", "Base", 22),
        ("Two", "One", 30),
        ("Two", "Meta", 30),
    ]
    assert all(m.file == "kinds.py" for m in mutants)
    assert "\nclass One:\n" in mutants[1].source
    assert "\nclass Two(Meta, metaclass=abc.ABCMeta):\n" in mutants[2].source
    assert "\nclass Two(One, metaclass=abc.ABCMeta):\n" in mutants[3].source
    for mutant in mutants:
        ast.parse(mutant.source)
        assert mutant.source.count("\n") == original.count("\n")


def test_drop_base_handles_a_header_over_several_lines(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path / "pkg",
        {
            "m.py": (
                "class A: pass\n\n\n"
                "class B(  # the base\n"
                "    A,\n"
                "):\n"
                "    x = 1\n"
            )
        },
    )

    [mutant] = _by(root, "drop_base")

    assert mutant.function == "B"
    assert "class B:\n    x = 1\n" in mutant.source
    ast.parse(mutant.source)


def test_concretize_base_makes_an_abstract_class_concrete(tmp_path: Path) -> None:
    root = _write_tree(tmp_path / "pkg", dict(_KINDS))

    mutants = _by(root, "concretize_base")

    # A class with an abstract marker of its own: ABC or ABCMeta among its
    # bases, or an @abstractmethod method. Two has only the metaclass.
    assert [(m.function, m.line) for m in mutants] == [
        ("Base", 5),
        ("Meta", 17),
        ("Two", 30),
    ]
    base = mutants[0].source
    assert "class Base:\n    def size(self) -> float:\n" in base
    assert "    def name(self) -> str: ...\n" in base
    assert "abstractmethod\n    def" not in base.split("class Meta")[0]
    # The import may stay; the rest of the module does not change.
    assert base.startswith("from abc import ABC, abstractmethod\nimport abc\n")
    assert "class Meta(metaclass=abc.ABCMeta):\n    @abstractmethod" in base
    assert "class Meta:\n    def run(self): ...\n" in mutants[1].source
    assert "class Two(One, Meta):\n" in mutants[2].source
    for mutant in mutants:
        ast.parse(mutant.source)


def test_concretize_base_drops_a_protocol_base(tmp_path: Path) -> None:
    root = _write_tree(
        tmp_path / "pkg",
        {
            "m.py": (
                "import typing\n"
                "from typing import Protocol\n\n\n"
                "class P(Protocol):\n"
                "    def run(self) -> int: ...\n\n\n"
                "class Q(typing.Protocol):\n"
                "    def run(self) -> int: ...\n"
            )
        },
    )

    mutants = _by(root, "concretize_base")

    assert [m.function for m in mutants] == ["P", "Q"]
    assert "\nclass P:\n" in mutants[0].source
    assert "\nclass Q:\n" in mutants[1].source


_INJECTED = {
    "__init__.py": "",
    "pricing.py": (
        "from __future__ import annotations\n\n"
        "from .discounts import Discount\n\n\n"
        "class Calc:\n"
        "    def __init__(self, discount: Discount, rate=1) -> None:\n"
        "        self.discount = discount\n"
        "        self.rate = rate\n\n"
        "    def total(self, prices):\n"
        "        return self.discount.apply(sum(prices)) * self.rate\n"
    ),
    "discounts.py": (
        "from abc import ABC, abstractmethod\n"
        "from dataclasses import dataclass\n"
        "from typing import Protocol\n\n\n"
        "class Discount(Protocol):\n"
        "    def apply(self, amount): ...\n\n\n"
        "class Base(ABC):\n"
        "    @abstractmethod\n"
        "    def apply(self, amount): ...\n\n\n"
        "@dataclass\n"
        "class Fixed:\n"
        "    value: float\n\n\n"
        "class Half(Base):\n"
        "    def __init__(self, ratio=0.5, *, rounding=None):\n"
        "        self.ratio = ratio\n\n"
        "    def apply(self, amount):\n"
        "        return amount * self.ratio\n\n\n"
        "class Percent:\n"
        "    def __init__(self, percent):\n"
        "        self.percent = percent\n\n\n"
        "class Zero(Base):\n"
        "    def apply(self, amount):\n"
        "        return amount\n"
    ),
}


def test_hardcode_collaborator_builds_the_first_class_needing_no_arguments(
    tmp_path: Path,
) -> None:
    root = _write_tree(tmp_path / "pkg", dict(_INJECTED))

    mutants = [
        m
        for m in generate_mutants(
            root, ["hardcode_collaborator"], instantiable=["discounts"]
        )
        if m.file == "pricing.py"
    ]

    # One mutant per collaborator the constructor keeps. The class is the
    # first by name that can be built without arguments: Base is abstract,
    # Discount a protocol, Fixed a dataclass with a required field.
    assert [(m.function, m.collaborator, m.member, m.line) for m in mutants] == [
        ("Calc.__init__", "discount", "Half", 9),
        ("Calc.__init__", "rate", "Half", 10),
    ]
    assert mutants[0].owner == "Calc"
    assert mutants[0].file == "pricing.py"
    assert mutants[0].description == (
        "pricing: Calc.__init__ builds its own discount as Half() (line 9)"
    )
    source = mutants[0].source
    # The import follows the module's own import of that module.
    assert source.startswith(
        "from __future__ import annotations\n\n"
        "from .discounts import Discount\n"
        "from .discounts import Half\n"
    )
    assert "        self.discount = Half()\n        self.rate = rate\n" in source
    for mutant in mutants:
        ast.parse(mutant.source)


def test_hardcode_collaborator_reuses_the_module_s_own_names(tmp_path: Path) -> None:
    files = dict(_INJECTED)
    files["pricing.py"] = (
        "from . import discounts\n\n\n"
        "class Calc:\n"
        "    def __init__(self, discount):\n"
        "        self.discount = discount\n"
    )
    files["shop.py"] = (
        "from .discounts import Zero, Half as H\n\n\n"
        "class Shop:\n"
        "    def __init__(self, discount):\n"
        "        self.discount = discount\n"
    )
    root = _write_tree(tmp_path / "pkg", files)

    mutants = generate_mutants(
        root, ["hardcode_collaborator"], instantiable=["discounts"]
    )

    by_file = {m.file: m for m in mutants}
    assert "        self.discount = discounts.Half()\n" in by_file["pricing.py"].source
    assert "        self.discount = H()\n" in by_file["shop.py"].source
    # Nothing is imported when the module has the name already.
    assert by_file["pricing.py"].source.count("import") == 1
    assert by_file["shop.py"].source.count("import") == 1


def test_hardcode_collaborator_without_a_class_to_build_makes_nothing(
    tmp_path: Path,
) -> None:
    root = _write_tree(tmp_path / "pkg", dict(_INJECTED))

    # pricing holds only Calc, whose constructor needs its collaborators.
    assert (
        generate_mutants(root, ["hardcode_collaborator"], instantiable=["pricing"])
        == []
    )


def test_hardcode_collaborator_by_default_builds_any_other_project_class(
    tmp_path: Path,
) -> None:
    root = _write_tree(tmp_path / "pkg", dict(_INJECTED))

    mutants = _by(root, "hardcode_collaborator")

    # Every project module, but never the class of the constructor itself:
    # Half keeps a ratio, which becomes the next class by name, Zero (its
    # abstract base needs no arguments either).
    assert [(m.owner, m.collaborator, m.member) for m in mutants] == [
        ("Half", "ratio", "Zero"),
        ("Percent", "percent", "Half"),
        ("Calc", "discount", "Half"),
        ("Calc", "rate", "Half"),
    ]
    # A class of the module itself needs no import.
    assert mutants[0].source.count("import") == _INJECTED["discounts.py"].count(
        "import"
    )
    assert "        self.ratio = Zero()\n" in mutants[0].source


def test_drop_call_names_the_method_it_changes(root: Path) -> None:
    mutants = _by(root, "drop_call")

    assert {m.function for m in mutants} == {"Service.place"}


# Review of N5: the injection operators see an annotated assignment, a
# function strategy called directly, and only the parameters a task spies.
_ANNOTATED = {
    "__init__.py": "",
    "pricing.py": (
        "from .discounts import Discount\n\n\n"
        "class Calc:\n"
        "    def __init__(self, discount: Discount, rate: float) -> None:\n"
        "        self.discount: Discount = discount\n"
        "        self.rate = rate\n\n"
        "    def total(self, prices):\n"
        "        return self.discount.apply(sum(prices)) * self.rate\n"
    ),
    "discounts.py": (
        "class Discount:\n" "    def apply(self, amount):\n" "        return amount\n"
    ),
}


def test_injection_operators_see_an_annotated_assignment(tmp_path: Path) -> None:
    root = _write_tree(tmp_path / "pkg", dict(_ANNOTATED))

    hardcoded = generate_mutants(
        root, ["hardcode_collaborator"], instantiable=["discounts"]
    )
    rebuilt = _by(root, "rebuild_injected")
    dropped = _by(root, "drop_call")

    assert [(m.collaborator, m.line) for m in hardcoded] == [
        ("discount", 6),
        ("rate", 7),
    ]
    assert "        self.discount: Discount = Discount()\n" in hardcoded[0].source
    assert [m.collaborator for m in rebuilt] == ["discount", "rate"]
    assert "        self.discount: Discount = type(discount)()\n" in rebuilt[0].source
    # The collaborator of the call is the parameter the attribute was given.
    assert [(m.collaborator, m.member) for m in dropped] == [("discount", "apply")]


def test_hardcode_collaborator_only_hardcodes_the_parameters_given_a_spy(
    tmp_path: Path,
) -> None:
    root = _write_tree(tmp_path / "pkg", dict(_ANNOTATED))

    mutants = generate_mutants(
        root,
        ["hardcode_collaborator"],
        instantiable=["discounts"],
        spied={("pricing.py", "Calc"): frozenset({"discount"})},
    )
    # A class the task gives no spy to keeps its constructor.
    none = generate_mutants(
        root, ["hardcode_collaborator"], instantiable=["discounts"], spied={}
    )

    assert [m.collaborator for m in mutants] == ["discount"]
    assert none == []


_ACTIONS = {
    "adventure.py": (
        "class Log:\n"
        "    def __init__(self):\n"
        "        self.lines = []\n\n\n"
        "class Action:\n"
        "    def __init__(self, name, execute):\n"
        "        self.name = name\n"
        "        self.execute = execute\n"
        "        self.log = Log()\n\n"
        "    def run(self, state):\n"
        "        result = self.execute(state)\n"
        "        self.execute(state)\n"
        "        self.name(state)\n"
        "        return f'{self.name}: {result}'\n\n\n"
        "def take(state):\n"
        "    return 'taken'\n"
    ),
}


def test_drop_call_cuts_a_call_of_a_function_the_constructor_was_given(
    tmp_path: Path,
) -> None:
    root = _write_tree(tmp_path / "flat", dict(_ACTIONS))

    mutants = _by(root, "drop_call")

    # self.execute holds a parameter, so calling it is a call of the
    # collaborator; so is self.name, which holds a parameter too.
    assert [(m.collaborator, m.member, m.line) for m in mutants] == [
        ("execute", "", 13),
        ("execute", "", 14),
        ("name", "", 15),
    ]
    by_line = {m.line: m for m in mutants}
    assert "        result = state\n" in by_line[13].source
    assert "        pass\n        self.name(state)\n" in by_line[14].source
    assert by_line[13].description == (
        "adventure: Action.run no longer calls self.execute "
        "(line 13, its first argument passed through)"
    )


_BUILDABLE = {
    "__init__.py": "",
    "pricing.py": (
        "class Calc:\n"
        "    def __init__(self, discount):\n"
        "        self.discount = discount\n"
    ),
    "discounts.py": (
        "from abc import ABC, abstractmethod\n"
        "from dataclasses import dataclass\n\n\n"
        "class Base(ABC):\n"
        "    @abstractmethod\n"
        "    def apply(self, amount): ...\n\n\n"
        "class AHalf(Base):\n"
        "    pass\n\n\n"
        "@dataclass\n"
        "class Fixed:\n"
        "    value: float\n\n\n"
        "@dataclass\n"
        "class BFixed(Fixed):\n"
        "    note: str = ''\n\n\n"
        "class CMiddle(Base):\n"
        "    def apply(self, amount):\n"
        "        return amount\n\n\n"
        "class DLeaf(CMiddle):\n"
        "    pass\n"
    ),
}


def test_hardcode_collaborator_skips_classes_that_cannot_be_built(
    tmp_path: Path,
) -> None:
    root = _write_tree(tmp_path / "pkg", dict(_BUILDABLE))

    mutants = generate_mutants(
        root, ["hardcode_collaborator"], instantiable=["discounts"]
    )

    # AHalf leaves the abstract apply unimplemented; BFixed inherits the
    # required field of Fixed. CMiddle implements apply.
    assert [m.member for m in mutants] == ["CMiddle"]


def test_hardcode_collaborator_imports_absolutely_in_a_flat_reference(
    tmp_path: Path,
) -> None:
    files = {name: text for name, text in _BUILDABLE.items() if name != "__init__.py"}
    root = _write_tree(tmp_path / "flat", files)

    (mutant,) = generate_mutants(
        root, ["hardcode_collaborator"], instantiable=["discounts"]
    )

    assert mutant.source.startswith("from discounts import CMiddle\n")
    assert "        self.discount = CMiddle()\n" in mutant.source


def test_hardcode_collaborator_targets_classes_by_qualified_name(
    tmp_path: Path,
) -> None:
    root = _write_tree(tmp_path / "pkg", dict(_BUILDABLE))

    mutants = generate_mutants(
        root, ["hardcode_collaborator"], instantiable=["discounts.DLeaf"]
    )

    assert [m.member for m in mutants] == ["DLeaf"]


# N7: a game whose objects live in module globals (``world.SACK``,
# ``world.here``), whose lists a method other than the constructor makes
# (``reset``), in a project base of the owner class; the actions get only
# the words of the command.
_GLOBALS = {
    "__init__.py": "",
    "world.py": (
        "class Holder:\n"
        "    def __init__(self):\n"
        "        self.label = ''\n\n"
        "    def reset(self):\n"
        "        self.things = []\n"
        "        self._seen = set()\n\n"
        "    def pop(self, name):\n"
        "        return None\n\n\n"
        "class Sack(Holder):\n"
        "    def __init__(self):\n"
        "        super().__init__()\n"
        "        self._limit = 2\n\n\n"
        "class Room(Holder):\n"
        "    pass\n\n\n"
        "SACK = Sack()\n"
        "here: Room = None\n"
        "OTHER = 3\n"
    ),
    "actions.py": (
        "from . import world\n"
        "from .world import SACK as BAG\n\n\n"
        "def drop(words):\n"
        "    thing = world.SACK.pop(words[1])\n"
        "    return thing\n\n\n"
        "def take(words):\n"
        "    thing = world.here.pop(words[1])\n"
        "    return thing\n\n\n"
        "def peek(words):\n"
        "    size = len(words)\n"
        "    BAG.pop(words[0])\n"
        "    return size\n\n\n"
        "def shadow(world):\n"
        "    world.SACK.pop('x')\n"
    ),
    "absolute.py": (
        "import pkg.world as w\n\n\n" "def drop(words):\n" "    w.SACK.pop(words[1])\n"
    ),
}


def test_container_operators_reach_objects_module_globals_hold(
    tmp_path: Path,
) -> None:
    root = _write_tree(tmp_path / "pkg", _GLOBALS)
    original = (root / "actions.py").read_text(encoding="utf-8")

    public = _by(root, "mutate_public_container")
    private = _by(root, "mutate_private_container")

    # Through the imported module, a name imported from it, and the package's
    # own name; a parameter that shadows the module is no global.
    assert [(m.file, m.function, m.owner, m.member) for m in public] == [
        ("absolute.py", "drop", "Sack", "things"),
        ("actions.py", "drop", "Sack", "things"),
        ("actions.py", "take", "Room", "things"),
        ("actions.py", "peek", "Sack", "things"),
    ]
    assert [_inserted(original, m.source) for m in public[1:]] == [
        ["    world.SACK.things.append(0)"],
        ["    world.here.things.append(0)"],
        ["    BAG.things.append(0)"],
    ]
    assert [(m.function, m.member) for m in private if m.file == "actions.py"] == [
        ("drop", "_seen"),
        ("take", "_seen"),
        ("peek", "_seen"),
    ]


def test_foreign_write_and_private_read_reach_module_globals(tmp_path: Path) -> None:
    root = _write_tree(tmp_path / "pkg", _GLOBALS)
    original = (root / "actions.py").read_text(encoding="utf-8")

    writes = [m for m in _by(root, "foreign_write") if m.file == "actions.py"]
    reads = [m for m in _by(root, "read_private_attribute") if m.file == "actions.py"]

    # A private data attribute first (the sack's own ``_limit``, else one a
    # base's method assigns); ``member`` names the attribute written.
    assert [(m.function, m.owner, m.member) for m in writes] == [
        ("drop", "Sack", "_limit"),
        ("take", "Room", "_seen"),
        ("peek", "Sack", "_limit"),
    ]
    assert _inserted(original, writes[0].source) == [
        "    world.SACK._limit = world.SACK._limit"
    ]
    assert [(m.function, m.member) for m in reads] == [
        ("drop", "_limit"),
        ("take", "_seen"),
        ("peek", "_limit"),
    ]
    assert _inserted(original, reads[0].source) == ["    _ = world.SACK._limit"]
    # The read follows the first use of the global's object, not the first
    # line: a global still ``None`` there (set by ``initialize()``) would
    # crash the mutant before the case could see the read.
    peek = reads[2].source.splitlines()
    assert peek.index("    _ = BAG._limit") == peek.index("    BAG.pop(words[0])") + 1


_NESTED = {
    "__init__.py": "",
    "model.py": (
        "class Item:\n"
        "    def __init__(self, price):\n"
        "        self._price = price\n"
        "        self._tags = []\n\n"
        "    def tag(self, t):\n"
        "        self._tags.append(t)\n\n\n"
        "class Cart:\n"
        "    def __init__(self):\n"
        "        self.items = []\n\n"
        "    def total(self):\n"
        "        def price_of(it):\n"
        "            p = it.price_hint\n"
        "            return p\n"
        "        try:\n"
        "            data = open('x.txt').read()\n"
        "        except OSError as e:\n"
        "            msg = e.args\n"
        "        words = 'a b'.split()\n"
        "        n = words.count\n"
        "        return sum(price_of(i) for i in self.items)\n\n"
        "    def stock(self, item):\n"
        "        def later():\n"
        "            item.tag('x')\n"
        "        return later\n\n\n"
        "def restock(item: Item, names):\n"
        "    def one(n):\n"
        "        item.tag(n)\n"
        "    for n in names:\n"
        "        one(n)\n"
        "    return item\n"
    ),
}


def test_object_operators_skip_nested_functions_and_objects_of_no_project_class(
    tmp_path: Path,
) -> None:
    """A nested function's body runs only if something calls it, and an
    object of no project class (``except ... as e``, a builtin-typed local)
    has no state a marker guards: a write there, ``e.args = e.args``, can
    never be killed (audit E2)."""
    root = _write_tree(tmp_path / "pkg", _NESTED)

    found = [
        (m.operator, m.function, m.member)
        for operator in (
            "foreign_write",
            "mutate_private_container",
            "read_private_attribute",
        )
        for m in _by(root, operator)
    ]

    # Only the parameters ``item`` (an ``Item`` by its annotation, or by the
    # ``tag`` called on it), read first thing; their one method call is in a
    # nested function, so no write follows a call.
    assert found == [
        ("read_private_attribute", "Cart.stock", "_price"),
        ("read_private_attribute", "restock", "_price"),
    ]


def test_a_virtual_environment_in_the_project_is_no_project_code(
    tmp_path: Path,
) -> None:
    """A ``venv`` (or ``.venv``) a student hands in holds library code: no
    module of it is mutated, as the static discovery skips it (audit E3)."""
    root = _write_tree(
        tmp_path / "pkg",
        {
            "main.py": "def f(x):\n    return x\n",
            "venv/lib/pygments/util.py": "def g(x):\n    return x\n",
            ".venv/lib/util.py": "def h(x):\n    return x\n",
            "build/venv/tool.py": "def k(x):\n    return x\n",
        },
    )

    assert {m.file for m in generate_mutants(root)} == {"main.py"}


def test_a_file_saved_with_a_byte_order_mark_or_a_coding_line_is_mutated(
    tmp_path: Path,
) -> None:
    """A file is read as Python reads it: UTF-8 with a BOM (Notepad), or in
    the encoding its coding line names (audit E5)."""
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "bom.py").write_bytes(b"\xef\xbb\xbfdef f(x):\n    return x\n")
    (root / "cp.py").write_bytes(
        "# -*- coding: cp1250 -*-\n# hruška\ndef g(x):\n    return x\n".encode("cp1250")
    )

    mutants = _by(root, "add_io_call")

    assert {(m.file, m.function) for m in mutants} == {("bom.py", "f"), ("cp.py", "g")}
    bom = next(m for m in mutants if m.file == "bom.py")
    assert bom.source.startswith("def f(x):\n")
    # A mutant is a text written as UTF-8: its coding line says so.
    cp = next(m for m in mutants if m.file == "cp.py")
    assert cp.source.startswith("# -*- coding: utf-8 -*-\n# hruška\n")


def test_an_undecodable_file_is_skipped_with_its_reason(tmp_path: Path) -> None:
    """A file Python itself cannot decode (cp1250 without a coding line) is
    no module to mutate: it is left out, and why is recorded, instead of a
    ``UnicodeDecodeError`` ending the whole run (audit E5)."""
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "main.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    (root / "cp.py").write_bytes("# hruška\ndef g(x):\n    return x\n".encode("cp1250"))
    skipped: list[tuple[str, str]] = []

    mutants = generate_mutants(root, ["add_io_call"], skipped=skipped)

    assert {m.file for m in mutants} == {"main.py"}
    assert [file for file, _ in skipped] == ["cp.py"]
    assert "does not decode as UTF-8" in skipped[0][1]


def test_stub_role_call_follows_imports_through_the_package_name(
    tmp_path: Path,
) -> None:
    """``from game.grades import average`` and ``import game.grades as gg``
    name the project module ``grades`` by the root package's own name; their
    calls are stubbed as the relative import's are (audit E6)."""
    root = _write_tree(
        tmp_path / "game",
        {
            "__init__.py": "",
            "grades.py": "def average(xs):\n    return sum(xs) / len(xs)\n",
            "app.py": (
                "from game.grades import average\n"
                "from . import grades\n"
                "import game.grades as gg\n\n\n"
                "def main(xs):\n"
                "    a = average(xs)\n"
                "    b = grades.average(xs)\n"
                "    c = gg.average(xs)\n"
                "    return a, b, c\n"
            ),
        },
    )

    [mutant] = _by(root, "stub_role_call")

    assert (mutant.file, mutant.function, mutant.member) == ("app.py", "main", "grades")
    assert mutant.source.count("(lambda *a, **k: None)(xs)") == 3


_STUBS = {
    "__init__.py": "",
    "other.py": "X = 1\n",
    "shapes.py": (
        "from abc import ABC, abstractmethod\n"
        "from typing import Protocol\n\n\n"
        "class Port(Protocol):\n"
        "    def save(self, x):\n"
        "        ...\n\n\n"
        "class Shape(ABC):\n"
        "    @abstractmethod\n"
        "    def area(self):\n"
        '        """Area."""\n\n'
        "    def name(self):\n"
        "        raise NotImplementedError\n\n"
        "    def todo(self):\n"
        '        """Later."""\n'
        "        pass\n\n\n"
        "class Square(Shape):\n"
        "    def __init__(self, side=1):\n"
        "        self._side = side\n\n"
        "    def area(self):\n"
        "        return self._side ** 2\n"
    ),
}


@pytest.mark.parametrize(
    "operator",
    ["lazy_import", "dynamic_import", "add_io_call", "add_io_via_helper"],
)
def test_code_that_never_runs_gets_no_mutant(tmp_path: Path, operator: str) -> None:
    """An abstract method, and a body that is only a docstring, ``...``,
    ``pass`` or ``raise NotImplementedError``, never runs as a case calls
    it: a mutant there could not be killed (audit E7)."""
    root = _write_tree(tmp_path / "pkg", _STUBS)
    original = _STUBS["shapes.py"].splitlines()

    mutants = [m for m in _by(root, operator) if m.file == "shapes.py"]

    assert mutants
    for mutant in mutants:
        lines = mutant.source.splitlines()
        # The first line that differs is the inserted one; what follows it is
        # the body of the method it went into.
        at = next(i for i, (a, b) in enumerate(zip(original, lines)) if a != b)
        assert original[at].strip() in (
            "self._side = side",
            "return self._side ** 2",
        ), (mutant.description, lines[at])


def _helpers_source() -> (
    tuple[dict[str, list[ast.ClassDef]], dict[str, ast.FunctionDef]]
):
    tree = ast.parse(
        "class Item:\n"
        "    def tag(self):\n"
        "        pass\n\n\n"
        "class Box:\n"
        "    def tag(self):\n"
        "        pass\n\n\n"
        "def none_first(flag):\n"
        "    found = None\n"
        "    if flag:\n"
        "        found = Item()\n"
        "    found.tag()\n\n\n"
        "def zero_first(flag):\n"
        "    found = 0\n"
        "    found = Item()\n"
        "    found.tag()\n\n\n"
        "def two_classes(flag):\n"
        "    found = None\n"
        "    found = Item()\n"
        "    found = Box()\n"
        "    found.tag()\n\n\n"
        "def only_none():\n"
        "    found = None\n"
        "    found.tag()\n\n\n"
        "def shadowed(item):\n"
        "    item.tag()\n\n"
        "    def inner(item):\n"
        "        item.zap()\n\n"
        "    return [item.zip() for item in range(3)], lambda item: item.zop()\n\n\n"
        "def decorated(item):\n"
        "    @item.register\n"
        "    def inner(x=item.size):\n"
        "        return item.inside\n\n"
        "    class Local(item.Base):\n"
        "        pass\n"
    )
    classes: dict[str, list[ast.ClassDef]] = {}
    functions: dict[str, ast.FunctionDef] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.setdefault(node.name, []).append(node)
        elif isinstance(node, ast.FunctionDef):
            functions[node.name] = node
    return classes, functions


def test_a_local_first_set_to_none_holds_the_class_it_is_built_of() -> None:
    """``found = None`` before ``found = Item()`` says no class: the local
    holds an ``Item``; another builtin value (``0``) or a second class does
    make it unknown."""
    from pythonarchtesting.mutation.objects import object_class

    classes, functions = _helpers_source()

    def of(name: str) -> object:
        found = object_class(classes, functions[name], "found", [])
        return found.name if found is not None else None

    assert of("none_first") == "Item"
    assert of("zero_first") is None
    assert of("two_classes") is None
    assert of("only_none") is None


def test_methods_called_on_a_name_are_those_the_function_itself_calls() -> None:
    """A nested function, comprehension or lambda binds a name of its own:
    ``item.zap()`` there is no call on the parameter ``item``."""
    from pythonarchtesting.mutation.functions import called_on

    _, functions = _helpers_source()

    assert called_on(functions["shadowed"], "item") == {"tag"}


def test_a_nested_definition_s_decorators_defaults_and_bases_run_in_the_function() -> (
    None
):
    from pythonarchtesting.mutation.functions import body_nodes

    _, functions = _helpers_source()

    read = {
        ast.unparse(node)
        for node in body_nodes(functions["decorated"])
        if isinstance(node, ast.Attribute)
    }

    assert read == {"item.register", "item.size", "item.Base"}
