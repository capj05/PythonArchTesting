"""Which calls of ``isinstance`` and ``type`` ``forbid_runtime_calls`` keeps:
only those that branch on the type of an object (review of N4)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from pythonarchtesting.execution.evaluators.type_tests import TypeTests

_SHAPES = "class Shape:\n    pass\n\n\nclass Circle(Shape):\n    pass\n"


def _function(parameters: str, line: str) -> str:
    """A function whose line 2 is ``line``, with a body when it opens one."""
    body = "\n        pass\n" if line.endswith(":") else "\n"
    return f"def f({parameters}):\n    {line}{body}"


def _tests(tmp_path: Path, client: str) -> TypeTests:
    # A client that does not parse would count by doubt and prove nothing.
    ast.parse(client)
    (tmp_path / "shapes.py").write_text(_SHAPES, encoding="utf-8")
    (tmp_path / "report.py").write_text(client, encoding="utf-8")
    return TypeTests(tmp_path)


@pytest.mark.parametrize(
    ("line", "kept"),
    [
        # A test against a project class is a branch on the type.
        ("if isinstance(shape, Circle):", True),
        ("if isinstance(shape, shapes.Circle):", True),
        ("if isinstance(shape, (int, Circle)):", True),
        # A class computed at run time cannot be told: it counts.
        ("if isinstance(shape, kinds[0]):", True),
        # Validating input against builtin types is no such branch.
        ("if not isinstance(shapes, list):", False),
        ("if isinstance(a, (int, float)):", False),
    ],
)
def test_isinstance_counts_only_against_a_project_class(
    tmp_path: Path, line: str, kept: bool
) -> None:
    tests = _tests(tmp_path, _function("shape, shapes, a, kinds", line))

    assert tests.is_type_test("builtins:isinstance", "report.py", 2) is kept


@pytest.mark.parametrize(
    ("line", "kept"),
    [
        ("if type(shape) == Circle:", True),
        ("if type(shape) is not Circle:", True),
        ('if type(shape).__name__ == "Circle":', True),
        ("if type(shape) in (Circle, Shape):", True),
        ("x = handlers[type(shape)]", True),
        ("match type(shape):\n        case _:\n            pass", True),
        # Only displayed: no decision depends on it.
        ('x = f"{type(shape).__name__} {shape}"', False),
        # Anything else decides by doubt: kept for later, keyed, compared.
        ("x = type(shape)", True),
        ("if type(shape) < 3:", True),
        ("x = handlers.get(type(shape))", True),
        ('x = "a " + type(shape).__name__', False),
        ('if "a " + type(shape).__name__ == "a Circle":', True),
        ("print(type(shape))", False),
        ("x = str(type(shape))", False),
        ('if f"{type(shape).__name__}" == "Circle":', True),
        ("x = type(shape).__name__", True),
    ],
)
def test_type_counts_only_when_its_result_decides(
    tmp_path: Path, line: str, kept: bool
) -> None:
    tests = _tests(tmp_path, _function("shape, handlers", line))

    assert tests.is_type_test("builtins:type", "report.py", 2) is kept


def test_what_cannot_be_read_counts(tmp_path: Path) -> None:
    tests = _tests(tmp_path, "def f(shape):\n    return shape\n")

    # No such file, no call on the line, no line: a type test, by doubt.
    assert tests.is_type_test("builtins:isinstance", "missing.py", 2) is True
    assert tests.is_type_test("builtins:isinstance", "report.py", 2) is True
    assert tests.is_type_test("builtins:type", "report.py", None) is True
    assert TypeTests(None).is_type_test("builtins:type", "report.py", 2) is True
    # Any other callee is not this module's to judge.
    assert tests.is_type_test("builtins:print", "report.py", 2) is True
    assert tests.project_classes() == frozenset({"Shape", "Circle"})


_REVIEWED = (
    "from .shapes import Circle as C, Shape\n"
    "from numbers import Number as N\n"
    "import collections.abc\n"
    "SHAPES = (C, Shape)\n\n"
    "def f(x, self, xs):\n"
    "    a = isinstance(x, C)\n"  # 7
    "    b = isinstance(x, SHAPES)\n"  # 8
    "    c = isinstance(x, self.kind)\n"  # 9
    "    t = type(x)\n"  # 10
    "    e = t is Shape\n"  # 11
    "    d = {Shape: 1}.get(type(x))\n"  # 12
    "    g = isinstance(x, (int, float)) or isinstance(x, Shape)\n"  # 13
    "    h = isinstance(x, (int, float, str, bool, bytes, complex, type(None)))\n"  # 14
    "    i = isinstance(xs, (list, dict, set, tuple, frozenset))\n"  # 15
    "    j = isinstance(x, N) or isinstance(x, collections.abc.Mapping)\n"  # 16
    "    k = isinstance(x, (Exception, ValueError))\n"  # 17
)


@pytest.mark.parametrize(
    ("line", "kept"),
    [
        (7, True),  # an import alias of a project class
        (8, True),  # a tuple constant of project classes
        (9, True),  # a class held by an attribute
        (10, True),  # type() kept for later
        (12, True),  # type() as the key of a lookup
        (13, True),  # one of two calls on the line tests a project class
        (14, False),  # builtin types only
        (15, False),
        (16, False),  # numbers and collections.abc, also through an alias
        (17, False),  # builtin exceptions
    ],
)
def test_only_known_builtin_types_and_displayed_types_are_dropped(
    tmp_path: Path, line: int, kept: bool
) -> None:
    """A type test is kept unless it is plainly no branch on a project
    type: every class an isinstance names is a builtin or standard library
    one, or the result of type() is only displayed (review of N5)."""
    tests = _tests(tmp_path, _REVIEWED)
    callee = "builtins:type" if line in (10, 12) else "builtins:isinstance"

    assert tests.is_type_test(callee, "report.py", line) is kept


def test_a_project_class_named_like_a_builtin_counts(tmp_path: Path) -> None:
    tests = _tests(
        tmp_path,
        "from .shapes import Shape as list\n\n\ndef f(x):\n    return isinstance(x, list)\n",
    )

    assert tests.is_type_test("builtins:isinstance", "report.py", 5) is True


# Review of the N5 fix round: calls of ``type`` and ``isinstance`` that are
# no branch on the type of an object, and the ones that stay one.
@pytest.mark.parametrize(
    ("callee", "line", "kept"),
    [
        # type(None) is the class of None, not a question about an object.
        ("type", "isinstance(a, (int, float, type(None)))", False),
        ("type", "t = type(None)", False),
        # type(x) handed to isinstance/issubclass is its argument, not a test.
        ("type", "isinstance(a, type(shape))", False),
        ("type", "issubclass(type(a), int)", False),
        # type(self)(...) builds a new object of the same class.
        ("type", "return type(self)(a)", False),
        # Displayed by %-formatting, .format() or a logging call.
        ("type", 'raise TypeError("got %s" % type(a).__name__)', False),
        ("type", 'raise TypeError("got {}".format(type(a).__name__))', False),
        ("type", 'log.warning("got %s", type(a).__name__)', False),
        ("type", 'msg = "%s: %s" % (a, type(a))', False),
        ("type", 'logging.error("got %s", type(a))', False),
        # ... but a %-format compared, or a number's %, stays a test.
        ("type", 'ok = "%s" % type(a).__name__ == "Circle"', True),
        ("type", "n = type(a) % 2", True),
        ("type", "t = type(a)", True),
        ("type", "if type(a) is int:", True),
        # Exceptions from any module and typing aliases are no branch.
        ("isinstance", "if isinstance(e, json.JSONDecodeError):", False),
        ("isinstance", "if isinstance(e, ShapeError):", False),
        ("isinstance", "if isinstance(a, List):", False),
        ("isinstance", "if isinstance(a, typing.Sequence):", False),
        ("isinstance", "if isinstance(a, Circle):", True),
        ("isinstance", "if isinstance(a, bool) or isinstance(a, Circle):", True),
    ],
)
def test_no_type_test_after_the_n5_review(
    tmp_path: Path, callee: str, line: str, kept: bool
) -> None:
    client = (
        "import json\nimport logging\nimport typing\nfrom typing import List\n"
        "from .shapes import Circle\n\n\nclass ShapeError(Exception):\n    pass\n\n\n"
        + _function("self, a, e, shape, log", line)
    )
    tests = _tests(tmp_path, client)
    lineno = client.splitlines().index(f"    {line.splitlines()[0]}") + 1

    assert tests.is_type_test(f"builtins:{callee}", "report.py", lineno) is kept
