"""``forbid_private_access`` (ENC001): no private attribute read from outside.

A static check of the matched target function or method: every ``obj._x``
it reads, where ``obj`` is not its own ``self``/``cls`` and the code is not
in the body of the class that defines ``_x``, is a violation. Each violation
has a fact (``details.facts``, 1:1 with ``details.violations``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.cli import main

_RULE = "ENC001/forbid_private_access/v1"

_INVENTORY = (
    "class Inventory:\n"
    "    _made = 0\n\n"
    "    def __init__(self, stock=None):\n"
    "        self._stock = dict(stock or {})\n"
    "        self.log = []\n\n"
    "    def items(self):\n"
    "        return dict(self._stock)\n\n"
    "    def _check(self):\n"
    "        return True\n"
)

_REPORT = (
    "from .inventory import Inventory\n\n\n"
    "def report(inventory: Inventory) -> str:\n"
    "    {marker}\n"
    "    return str(sorted(inventory.items().items()))\n"
)

_HEADER = (
    "from typing import Annotated\n"
    "from pythonarchtesting.rules import forbid_private_access\n"
)


def _write(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True)
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    return root


def _marked(text: str, marker: str = "forbid_private_access()") -> str:
    return _HEADER + text.replace(
        "{marker}", f"__archtest__: Annotated[None, {marker}]"
    )


def _plain(text: str) -> str:
    """``text`` without its marker lines: the unannotated target."""
    return "".join(
        line for line in text.splitlines(keepends=True) if "{marker}" not in line
    )


def _run(
    tmp_path: Path, reference: dict[str, str], target: dict[str, str]
) -> list[dict[str, Any]]:
    source = _write(tmp_path / "reference", {"__init__.py": "", **reference})
    submission = _write(tmp_path / "target", {"__init__.py": "", **target})
    output = tmp_path / "report.json"
    main(
        [
            "--source",
            str(source),
            "--target",
            str(submission),
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    return [
        r
        for t in report["targets"]
        for r in t["results"]
        if str(r["rule_id"]).startswith("ENC001/")
    ]


def _report_run(tmp_path: Path, body: str, marker: str = "forbid_private_access()"):
    reference = {"inventory.py": _INVENTORY, "shop.py": _marked(_REPORT, marker)}
    target = {
        "inventory.py": _INVENTORY,
        "shop.py": _plain(_REPORT).replace(
            "    return str(sorted(inventory.items().items()))\n", body
        ),
    }
    return _run(tmp_path, reference, target)


def test_forbid_private_access_flags_foreign_read(tmp_path: Path) -> None:
    [result] = _report_run(
        tmp_path, "    return str(sorted(inventory._stock.items()))\n"
    )

    assert result["rule_id"] == _RULE
    assert result["status"] == "FAILED"
    details = result["details"]
    assert details["violation_count"] == 1
    assert details["facts"] == [
        {
            "kind": "read",
            "attribute": "_stock",
            "class": "Inventory",
            "file": "shop.py",
            "line": 5,
            "reader": "shop:report",
            # No `receiver`: `items` changes nothing, so the read is no part
            # of a write, and classify keeps it whatever the line holds.
        }
    ]
    assert "_stock" in details["violations"][0]
    assert "shop.py:5" in details["violations"][0]


def test_forbid_private_access_passes_the_public_interface(tmp_path: Path) -> None:
    [result] = _report_run(
        tmp_path, "    return str(sorted(inventory.items().items()))\n"
    )

    assert result["status"] == "OK", result


def test_forbid_private_access_class_is_null_without_annotation(tmp_path: Path) -> None:
    body = "    other = inventory\n    return str(other._stock)\n"

    [result] = _report_run(tmp_path, body)

    assert result["status"] == "FAILED"
    [fact] = result["details"]["facts"]
    assert fact["class"] is None and fact["attribute"] == "_stock"


_OWNER = (
    "class Inventory:\n"
    "    _made = 0\n\n"
    "    def __init__(self, stock=None):\n"
    "        self._stock = dict(stock or {})\n\n"
    "    def __eq__(self, other):\n"
    "        {marker}\n"
    "        return self._stock == other._stock\n\n"
    "    @classmethod\n"
    "    def made(cls):\n"
    "        {marker}\n"
    "        return cls._made + Inventory._made\n\n"
    "    def total(this):\n"
    "        {marker}\n"
    "        helper = lambda: this._stock\n"
    "        return sum(helper().values()) + super()._made + type(this)._made\n\n\n"
    "class Report:\n"
    "    def __init__(self):\n"
    "        self._lines = []\n\n"
    "    def show(self, inventory):\n"
    "        {marker}\n"
    "        return [self._lines, inventory]\n"
)


def test_forbid_private_access_allows_self_and_cls(tmp_path: Path) -> None:
    """``self``/``cls`` (whatever the first parameter is called), and another
    instance of the same class in a method of the class that defines the
    attribute (``other._stock`` in ``__eq__``), are no violation."""
    reference = {"inventory.py": _marked(_OWNER)}
    target = {"inventory.py": _plain(_OWNER)}

    results = _run(tmp_path, reference, target)

    assert len(results) == 4
    assert {r["status"] for r in results} == {"OK"}, results


def test_forbid_private_access_flags_another_class_in_a_method(tmp_path: Path) -> None:
    """In a method of another class, the object's private attribute is foreign,
    though the method's own ``self._lines`` is not."""
    reference = {"inventory.py": _marked(_OWNER)}
    changed = _OWNER.replace(
        "return [self._lines, inventory]", "return [self._lines, inventory._stock]"
    )
    target = {"inventory.py": _plain(changed)}

    results = _run(tmp_path, reference, target)

    failed = [r for r in results if r["status"] == "FAILED"]
    assert len(failed) == 1
    [fact] = failed[0]["details"]["facts"]
    assert fact["reader"] == "inventory:Report.show"
    assert fact["attribute"] == "_stock"


def test_forbid_private_access_allows_dunder(tmp_path: Path) -> None:
    body = (
        "    name = inventory.__class__.__name__\n"
        "    return name + str(inventory.__dict__)\n"
    )

    [result] = _report_run(tmp_path, body)

    assert result["status"] == "OK", result


def test_forbid_private_access_flags_a_name_mangled_attribute(tmp_path: Path) -> None:
    [result] = _report_run(tmp_path, "    return str(inventory.__secret)\n")

    assert result["status"] == "FAILED"
    assert [f["attribute"] for f in result["details"]["facts"]] == ["__secret"]


def test_forbid_private_access_allow_list(tmp_path: Path) -> None:
    body = "    print(inventory._stock)\n    return str(inventory._check())\n"

    [result] = _report_run(
        tmp_path, body, marker='forbid_private_access(allow=["_stock"])'
    )

    assert result["status"] == "FAILED"
    assert [f["attribute"] for f in result["details"]["facts"]] == ["_check"]


def test_forbid_private_access_facts_aligned_with_violations(tmp_path: Path) -> None:
    body = (
        "    lines = [f'{k}: {v}' for k, v in sorted(inventory._stock.items())]\n"
        "    total = sum(inventory._stock.values())\n"
        "    return str(lines) + str(total)\n"
    )

    [result] = _report_run(tmp_path, body)

    details = result["details"]
    assert len(details["facts"]) == len(details["violations"]) == 2
    for fact, text in zip(details["facts"], details["violations"]):
        assert f"shop.py:{fact['line']}" in text
    assert [f["line"] for f in details["facts"]] == [5, 6]


def test_forbid_private_access_leaves_writes_to_forbid_foreign_writes(
    tmp_path: Path,
) -> None:
    """Assigning or deleting the attribute, or an item of it, is a write:
    ``forbid_foreign_writes`` reports it; reading it to call a method is a
    read."""
    body = (
        "    inventory._stock = {}\n"
        "    inventory._stock['a'] = 1\n"
        "    inventory._stock['a'] -= 1\n"
        "    del inventory._stock['a']\n"
        "    inventory._stock.get('a')\n"
        "    return ''\n"
    )

    [result] = _report_run(tmp_path, body)

    assert [f["line"] for f in result["details"]["facts"]] == [9]


_HELPERS = "def _helper():\n    return 1\n"


def test_forbid_private_access_skips_private_names_of_modules(tmp_path: Path) -> None:
    """``module._helper`` is a module's private name, which ``module_interface``
    guards, not an attribute of an object; code outside functions (run at
    import time) is not checked either."""
    shop = (
        "import os\n"
        "from . import helpers\n"
        "from .inventory import Inventory\n\n"
        "LIMIT = Inventory()._stock\n\n\n"
        "def report(inventory: Inventory) -> str:\n"
        "    {marker}\n"
        "    return str(helpers._helper()) + str(os._exit is None)\n"
    )
    reference = {
        "inventory.py": _INVENTORY,
        "helpers.py": _HELPERS,
        "shop.py": _marked(shop),
    }
    target = {
        "inventory.py": _INVENTORY,
        "helpers.py": _HELPERS,
        "shop.py": _plain(shop),
    }

    [result] = _run(tmp_path, reference, target)

    assert result["status"] == "OK", result


def test_forbid_private_access_refuses_a_bad_allow(tmp_path: Path) -> None:
    reference = {
        "inventory.py": _INVENTORY,
        "shop.py": _marked(_REPORT, "forbid_private_access(allow=['stock', 3])"),
    }
    target = {"inventory.py": _INVENTORY, "shop.py": _plain(_REPORT)}

    results = _run(tmp_path, reference, target)

    assert results and all(r["status"] != "OK" for r in results)
    assert any("invalid" in str(r["rule_id"]) for r in results), results


def test_forbid_private_access_flags_a_mangled_name_written_out(tmp_path: Path) -> None:
    """``obj._Owner__x`` is how code outside the class reaches a ``__x``:
    private, and reported under the name written."""
    [result] = _report_run(tmp_path, "    return str(inventory._Inventory__stock)\n")

    assert result["status"] == "FAILED"
    assert [f["attribute"] for f in result["details"]["facts"]] == ["_Inventory__stock"]


def _owned(tmp_path: Path, text: str) -> list[dict[str, Any]]:
    """Results of ``text`` (one module, ``{marker}`` where the rule goes)
    with ``forbid_private_access()`` in the reference and none in the target."""
    return _run(tmp_path, {"model.py": _marked(text)}, {"model.py": _plain(text)})


def test_forbid_private_access_knows_attributes_a_tuple_assigns(
    tmp_path: Path,
) -> None:
    """``self._x, self._y = x, y`` (or ``*self._rest``) defines ``_x`` and
    ``_y`` as much as two assignments do: ``other._x`` in ``__eq__`` is the
    class's own business."""
    text = (
        "class Point:\n"
        "    def __init__(self, x, y, *rest):\n"
        "        self._x, self._y = x, y\n"
        "        [self._first, *self._rest] = rest or [0]\n\n"
        "    def __eq__(self, other):\n"
        "        {marker}\n"
        "        return (self._x, self._y, self._rest) == (\n"
        "            other._x, other._y, other._first\n"
        "        )\n"
    )

    [result] = _owned(tmp_path, text)

    assert result["status"] == "OK", result


def test_forbid_private_access_knows_attributes_of_project_base_classes(
    tmp_path: Path,
) -> None:
    """A subclass's ``__eq__`` reading ``other._stock``, which only its project
    base class defines, reads its own class's attribute."""
    shop = (
        "from .inventory import Inventory\n\n\n"
        "class Shelf(Inventory):\n"
        "    def __eq__(self, other):\n"
        "        {marker}\n"
        "        return self._stock == other._stock\n"
    )
    reference = {"inventory.py": _INVENTORY, "shop.py": _marked(shop)}
    target = {"inventory.py": _INVENTORY, "shop.py": _plain(shop)}

    [result] = _run(tmp_path, reference, target)

    assert result["status"] == "OK", result


def test_forbid_private_access_static_methods(tmp_path: Path) -> None:
    """A static method has no ``self``: in its own class it may read the
    attributes the class defines, in another class it may not."""
    text = (
        "class Money:\n"
        "    def __init__(self, cents):\n"
        "        self._cents = cents\n\n"
        "    @staticmethod\n"
        "    def total(a, b):\n"
        "        {marker}\n"
        "        return a._cents + b._cents\n\n\n"
        "class Till:\n"
        "    @staticmethod\n"
        "    def count(money):\n"
        "        {marker}\n"
        "        return money._cents\n"
    )

    results = _owned(tmp_path, text)

    by_target = {r["target"]["qualname"]: r for r in results}
    assert by_target["Money.total"]["status"] == "OK"
    assert by_target["Till.count"]["status"] == "FAILED"
    [fact] = by_target["Till.count"]["details"]["facts"]
    assert (fact["attribute"], fact["reader"]) == ("_cents", "model:Till.count")


def test_forbid_private_access_flags_a_read_in_a_nested_function(
    tmp_path: Path,
) -> None:
    """A closure or a local function of the client is the client's code."""
    body = (
        "    def stock():\n"
        "        return inventory._stock\n"
        "    total = (lambda: inventory._stock)()\n"
        "    return str(stock()) + str(total)\n"
    )

    [result] = _report_run(tmp_path, body)

    assert result["status"] == "FAILED"
    assert [(f["attribute"], f["line"]) for f in result["details"]["facts"]] == [
        ("_stock", 6),
        ("_stock", 7),
    ]


def test_forbid_private_access_allows_named_tuple_api_and_sunder_names(
    tmp_path: Path,
) -> None:
    """``_replace``, ``_asdict``, ``_fields``, ``_make`` and ``_field_defaults``
    are the public API of a named tuple, and ``_value_``/``_name_`` (sunder
    names) that of an enum member: no private reads."""
    text = (
        "import enum\n"
        "from collections import namedtuple\n\n"
        'Point = namedtuple("Point", "x y")\n\n\n'
        "class Colour(enum.Enum):\n"
        "    RED = 1\n\n\n"
        "def move(p: Point, c: Colour) -> tuple:\n"
        "    {marker}\n"
        "    moved = p._replace(x=p.x + 1)\n"
        "    again = Point._make(moved._asdict().values())\n"
        "    return (again, p._fields, p._field_defaults, c._value_, c._name_)\n"
    )

    [result] = _owned(tmp_path, text)

    assert result["status"] == "OK", result


def test_forbid_private_access_a_local_name_is_no_module(tmp_path: Path) -> None:
    """A parameter or local named like an imported module is the object, not
    the module: ``inventory._stock`` is a read of its private attribute."""
    shop = (
        "from . import inventory\n\n\n"
        'def report(inventory: "inventory.Inventory") -> str:\n'
        "    {marker}\n"
        "    return str(inventory._stock)\n"
    )
    reference = {"inventory.py": _INVENTORY, "shop.py": _marked(shop)}
    target = {"inventory.py": _INVENTORY, "shop.py": _plain(shop)}

    [result] = _run(tmp_path, reference, target)

    assert result["status"] == "FAILED", result
    assert [f["attribute"] for f in result["details"]["facts"]] == ["_stock"]


def test_forbid_private_access_flags_reads_by_name(tmp_path: Path) -> None:
    """``getattr(obj, "_x")``, ``vars(obj)["_x"]`` and ``obj.__dict__["_x"]``
    read ``_x`` too (a constant name); writing through them does not count."""
    body = (
        '    a = getattr(inventory, "_stock")\n'
        '    b = vars(inventory)["_stock"]\n'
        '    c = inventory.__dict__["_stock"]\n'
        '    inventory.__dict__["_other"] = 1\n'
        '    d = getattr(inventory, "items")\n'
        "    return str((a, b, c, d))\n"
    )

    [result] = _report_run(tmp_path, body)

    assert result["status"] == "FAILED"
    details = result["details"]
    assert len(details["facts"]) == len(details["violations"]) == 3
    assert [(f["attribute"], f["class"], f["line"]) for f in details["facts"]] == [
        ("_stock", "Inventory", 5),
        ("_stock", "Inventory", 6),
        ("_stock", "Inventory", 7),
    ]


def test_forbid_private_access_reports_a_chain_in_source_order(
    tmp_path: Path,
) -> None:
    [result] = _report_run(tmp_path, "    return str(inventory._stock._data)\n")

    assert [f["attribute"] for f in result["details"]["facts"]] == ["_stock", "_data"]


@pytest.mark.parametrize(
    "marker",
    ['forbid_private_access(alow=["_stock"])', 'forbid_private_access("_stock")'],
)
def test_forbid_private_access_refuses_unknown_parameters(
    tmp_path: Path, marker: str
) -> None:
    reference = {"inventory.py": _INVENTORY, "shop.py": _marked(_REPORT, marker)}
    target = {"inventory.py": _INVENTORY, "shop.py": _plain(_REPORT)}

    results = _run(tmp_path, reference, target)

    assert results and all(r["status"] != "OK" for r in results)
    assert all("invalid_declaration" in str(r["rule_id"]) for r in results), results


@pytest.mark.parametrize(
    ("code", "receivers"),
    [
        # The read that is the object of the method call is the write's own.
        ("inv._stock.update(other._stock)", [("inv", True), ("other", False)]),
        ("a._x = b._x", [("b", False)]),
        ("x = inv._log; inv._log = []", [("inv", False)]),
        # Only a method that changes the container makes the read the
        # write's: a copy read on a write line is a read of its own.
        ("inv._log.append(other._log.copy())", [("inv", True), ("other", False)]),
        ("a._x = b._x.copy()", [("b", False)]),
        # Rebuilding the very attribute the statement assigns is that write.
        ("inv._stock = {k: v for k, v in inv._stock.items()}", [("inv", True)]),
        (
            "inv._stock.setdefault(1, 0); other._stock.get(1)",
            [("inv", True), ("other", False)],
        ),
        # A deque and a set change in place too (review of N5).
        ("inv._log.appendleft(1); inv._log.extendleft([2])", [("inv", True)] * 2),
        ("x = inv._log.popleft()", [("inv", True)]),
        ("inv._seen.difference_update(other._seen)", [("inv", True), ("other", False)]),
        ("inv._seen.intersection_update({1})", [("inv", True)]),
        ("inv._seen.symmetric_difference_update({1})", [("inv", True)]),
    ],
)
def test_a_read_is_tagged_as_the_receiver_of_a_method_call(
    code: str, receivers: list[tuple[str, bool]]
) -> None:
    import ast

    from pythonarchtesting.execution.evaluators.private_access import private_reads

    function = ast.parse(f"def f(inv, other, a, b):\n    {code}\n").body[0]

    reads = private_reads(
        function, self_name=None, defined=set(), modules=set(), allow=set()
    )

    assert [(ast.unparse(r.value), r.receiver) for r in reads] == receivers


@pytest.mark.parametrize(
    ("code", "changes"),
    [
        ("a._x = b._x.setdefault(1, 0)", [("b", "mutated")]),
        ("inv._stock = {k: v for k, v in inv._stock.items()}", [("inv", "assigned")]),
        ("a._x = b._x", [("b", "")]),
    ],
)
def test_a_receiver_says_which_change_its_write_makes(
    code: str, changes: list[tuple[str, str]]
) -> None:
    """classify folds a receiver only into a write of the change it names,
    so b's read in ``a._x = b._x.setdefault(...)`` is not taken for part of
    the assignment of ``a._x`` (review of N5)."""
    import ast

    from pythonarchtesting.execution.evaluators.private_access import private_reads

    function = ast.parse(f"def f(inv, a, b):\n    {code}\n").body[0]

    reads = private_reads(
        function, self_name=None, defined=set(), modules=set(), allow=set()
    )

    assert [(ast.unparse(r.value), r.change) for r in reads] == changes


_TWO_ITEMS = (
    "class Inventory:\n"
    "    def __init__(self):\n"
    "        self._items = {}\n\n\n"
    "class Cart:\n"
    "    def __init__(self):\n"
    "        self._items = []\n\n"
    "    def checkout(self, inv):\n"
    "        {marker}\n"
    "        return inv._items\n\n"
    '    def __eq__(self, other: "Cart"):\n'
    "        {marker}\n"
    "        return self._items == other._items\n\n"
    '    def merged(self, other: "Cart"):\n'
    "        {marker}\n"
    "        fresh = type(self)()\n"
    "        copy: Cart = Cart()\n"
    "        return fresh._items + copy._items + other._items + Cart()._items\n\n"
    "    @classmethod\n"
    '    def joined(cls, a: "Cart", b: "model.Cart"):\n'
    "        {marker}\n"
    "        return cls()._items + a._items + b._items\n"
)


def test_forbid_private_access_a_shared_name_is_not_the_own_attribute(
    tmp_path: Path,
) -> None:
    """``inv._items`` in ``Cart.checkout`` reads the inventory's attribute,
    though ``Cart`` has an ``_items`` of its own: only a receiver known to be
    a ``Cart`` (annotated so, built by ``Cart()`` or ``type(self)()``, or
    ``cls``) reads the class's own business (audit E1)."""
    results = _owned(tmp_path, _TWO_ITEMS)

    by_target = {r["target"]["qualname"]: r for r in results}
    assert by_target["Cart.checkout"]["status"] == "FAILED"
    [fact] = by_target["Cart.checkout"]["details"]["facts"]
    assert (fact["attribute"], fact["reader"]) == ("_items", "model:Cart.checkout")
    for name in ("Cart.__eq__", "Cart.merged", "Cart.joined"):
        assert by_target[name]["status"] == "OK", by_target[name]


def test_forbid_private_access_a_name_only_the_family_defines_stays_own(
    tmp_path: Path,
) -> None:
    """An unannotated ``other`` still reads the class's own attribute when no
    project class outside the class's family defines that name: a subclass
    assigning it too does not make it foreign."""
    text = (
        "class Cart:\n"
        "    def __init__(self):\n"
        "        self._items = []\n\n"
        "    @classmethod\n"
        "    def copied(cls, other):\n"
        "        {marker}\n"
        "        return cls(other._items)\n\n\n"
        "class BigCart(Cart):\n"
        "    def __init__(self):\n"
        "        self._items = [1]\n"
    )

    results = _owned(tmp_path, text)

    assert [r["status"] for r in results] == ["OK"], results


def test_forbid_private_access_builds_the_class_lookup_once_per_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two marked methods of one target share one ``ProtocolEntityLookup``;
    each target gets its own."""
    from pythonarchtesting.protocols.entity_lookup import ProtocolEntityLookup

    built: list[int] = []
    original = ProtocolEntityLookup.from_entities.__func__  # type: ignore[attr-defined]

    def counting(cls: type, entities: Any) -> Any:
        built.append(len(entities))
        return original(cls, entities)

    monkeypatch.setattr(ProtocolEntityLookup, "from_entities", classmethod(counting))
    shop = (
        "from .inventory import Inventory\n\n\n"
        "class Shelf(Inventory):\n"
        "    def __eq__(self, other):\n"
        "        {marker}\n"
        "        return self._stock == other._stock\n\n"
        "    def same(self, other):\n"
        "        {marker}\n"
        "        return self._stock is other._stock\n"
    )
    reference = {"inventory.py": _INVENTORY, "shop.py": _marked(shop)}
    target = {"inventory.py": _INVENTORY, "shop.py": _plain(shop)}

    results = _run(tmp_path, reference, target)

    assert [result["status"] for result in results] == ["OK", "OK"]
    assert len(built) == 1


_ROOMS = (
    "class Player:\n"
    "    def __init__(self, name):\n"
    "        self._name = name\n"
    "{player_exits}\n\n"
    "class Room:\n"
    "    def __init__(self, name):\n"
    "        self._name = name\n"
    "        self._exits = []\n\n"
    "    def __eq__(self, other):\n"
    "        {marker}\n"
    "        return isinstance(other, Room) and self._name == other._name\n\n"
    "    def __lt__(self, other):\n"
    "        {marker}\n"
    "        return self._name < other._name\n\n"
    "    def same(self, other):\n"
    "        {marker}\n"
    "        if not isinstance(other, Room):\n"
    "            return False\n"
    "        return self._name == other._name\n\n"
    "    def either(self, other):\n"
    "        {marker}\n"
    "        if isinstance(other, (Room, Player)):\n"
    "            return other._name\n"
    "        return None\n\n"
    "    def guessed(self, other):\n"
    "        {marker}\n"
    "        return other._name if isinstance(other, Room) else ''\n\n"
    "    def too_early(self, other):\n"
    "        {marker}\n"
    "        name = other._name\n"
    "        return isinstance(other, Room) and name == self._name\n\n"
    "    def wrong_class(self, other):\n"
    "        {marker}\n"
    "        return isinstance(other, Player) and other._name == self._name\n\n"
    "    def __ne__(self, other: Player):\n"
    "        {marker}\n"
    "        return other._name\n\n"
    "    def connect(self, other):\n"
    "        {marker}\n"
    "        other._exits.append(self)\n"
)


@pytest.mark.parametrize("player_has_exits", [False, True])
def test_forbid_private_access_an_isinstance_check_or_a_dunder_knows_the_class(
    tmp_path: Path, player_has_exits: bool
) -> None:
    """``other`` is known to be a ``Room`` behind ``isinstance(other, Room)``
    (an ``if``, an ``and``, an early ``return``, a conditional expression) and
    as the other operand of a comparison or arithmetic dunder; elsewhere an
    unannotated ``other`` passes only while no class outside the family
    defines the name (``connect``)."""
    exits = "        self._exits = []\n" if player_has_exits else ""
    results = _owned(tmp_path, _ROOMS.replace("{player_exits}\n", exits))

    status = {r["target"]["qualname"]: r["status"] for r in results}
    assert status == {
        "Room.__eq__": "OK",
        "Room.__lt__": "OK",
        "Room.same": "OK",
        "Room.either": "OK",
        "Room.guessed": "OK",
        "Room.too_early": "FAILED",
        "Room.wrong_class": "FAILED",
        "Room.__ne__": "FAILED",
        "Room.connect": "FAILED" if player_has_exits else "OK",
    }


def test_forbid_private_access_a_class_of_another_module_is_not_the_own_one(
    tmp_path: Path,
) -> None:
    """``views.Item`` is not ``models.Item`` though both are called ``Item``:
    an annotation or a call naming a class through an import is resolved
    to that class; only a name that cannot be resolved is taken by its
    simple name."""
    models = (
        "from . import views\n"
        "from .views import Item as ViewItem\n\n\n"
        "class Item:\n"
        "    def __init__(self):\n"
        "        self._price = 1\n\n"
        '    def by_view(self, other: "views.Item"):\n'
        "        {marker}\n"
        "        return other._price\n\n"
        "    def by_alias(self, other: ViewItem):\n"
        "        {marker}\n"
        "        return other._price\n\n"
        "    def built(self):\n"
        "        {marker}\n"
        "        return views.Item()._price\n\n"
        "    def own(self, other: Item, third: 'models.Item'):\n"
        "        {marker}\n"
        "        return other._price + Item()._price + third._price\n"
    )
    views = "class Item:\n    def __init__(self):\n        self._price = 2\n"
    reference = {"models.py": _marked(models), "views.py": views}
    target = {"models.py": _plain(models), "views.py": views}

    results = _run(tmp_path, reference, target)

    status = {r["target"]["qualname"]: r["status"] for r in results}
    assert status == {
        "Item.by_view": "FAILED",
        "Item.by_alias": "FAILED",
        "Item.built": "FAILED",
        "Item.own": "OK",
    }
