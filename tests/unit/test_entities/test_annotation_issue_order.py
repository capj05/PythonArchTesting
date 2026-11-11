"""Characterisation of how a marker's arguments become params and issues.

The order of the issues in ``unsupported`` is visible in the declaration report:
the marker's own issues, then the tuple form, then an unknown name, then the
positional arguments, the list-valued check, the single-valued check and the
keywords. These cases pin that order together with the params, including the
protocol, ``enforce_flow``, ``required_attribute`` and ``flow`` special cases.
"""

from __future__ import annotations

import ast

import pytest

from pythonarchtesting.entities_extraction.annotations import (
    extract_annotation_declarations,
)

_SOURCE = """__archtest__: Annotated[
    None,
    forbid_imports(x, 1, "a", 2, flag=y),
    enforce_flow(["a", "b"], 3, f()),
    implements_protocol(Proto, 2, protocol=Other),
    implements_runtime_protocol(protocol="P"),
    required_attribute("n", 4, annotation=int, other=f(), **extra),
    flow("s", variable="v"),
    flow(stage="s"),
    foo(x, 1),
    ("kind", {"a": 1}),
    (name, {}),
    ("kind", {1: 2}),
    7,
] = 5
__archtest__: int
"""

_ASSIGNED = ("assigned_value", "5", 15, 4, {})


def _summary(declaration):
    issues = [
        (
            issue["kind"],
            issue["expr"],
            issue["lineno"],
            issue["col"],
            {
                key: value
                for key, value in issue.items()
                if key not in ("kind", "expr", "lineno", "col")
            },
        )
        for issue in declaration.unsupported
    ]
    return declaration.kind, declaration.params, issues, declaration.order


def test_params_and_issue_order_stay_as_they_were() -> None:
    declarations = extract_annotation_declarations(ast.parse(_SOURCE).body, _SOURCE)

    assert [_summary(declaration) for declaration in declarations] == [
        (
            "forbid_imports",
            {"forbidden": ["a"]},
            [
                _ASSIGNED,
                ("arg", "x", 3, 19, {"index": 0, "name": "forbid_imports"}),
                # A non-literal before them does not shift the literals' issues:
                # each one carries its own argument's index and position.
                ("arg", "1", 3, 22, {"index": 1, "name": "forbid_imports"}),
                ("arg", "2", 3, 30, {"index": 3, "name": "forbid_imports"}),
                ("kw", "y", 3, 38, {"name": "flag"}),
            ],
            0,
        ),
        (
            "enforce_flow",
            {"stages": ["a", "b"]},
            [
                _ASSIGNED,
                ("arg", "f()", 4, 32, {"index": 2, "name": "enforce_flow"}),
                ("arg", "3", 4, 29, {"index": 1, "name": "enforce_flow"}),
            ],
            1,
        ),
        (
            "implements_protocol",
            # The surplus ``2`` is reported but no longer stored as the protocol.
            {"protocol_expr": "Other"},
            [
                _ASSIGNED,
                ("arg", "2", 5, 31, {"index": 1, "name": "implements_protocol"}),
            ],
            2,
        ),
        (
            "implements_runtime_protocol",
            {"protocol": "P", "protocol_expr": "'P'"},
            [_ASSIGNED],
            3,
        ),
        (
            "required_attribute",
            {"name": "n", "annotation": "int"},
            [
                _ASSIGNED,
                ("arg", "4", 7, 28, {"index": 1, "name": "required_attribute"}),
                ("kw", "f()", 7, 53, {"name": "other"}),
                ("kw", "extra", 7, 60, {"name": "**"}),
            ],
            4,
        ),
        (
            "flow",
            {"stage": "s", "variable": "v", "variable_explicit": True},
            [_ASSIGNED],
            5,
        ),
        ("flow", {"stage": "s", "variable_explicit": False}, [_ASSIGNED], 6),
        (
            "foo",
            {},
            [
                _ASSIGNED,
                ("unknown_metadata", "foo(x, 1)", 10, 4, {"name": "foo"}),
                ("arg", "x", 10, 8, {"index": 0, "name": "foo"}),
            ],
            7,
        ),
        (
            "kind",
            {"a": 1},
            [
                _ASSIGNED,
                ("unknown_metadata", '("kind", {"a": 1})', 11, 4, {"name": "kind"}),
            ],
            8,
        ),
        (
            "unknown",
            {},
            [
                _ASSIGNED,
                ("metadata", "name", 12, 5, {}),
                ("metadata", "(name, {})", 12, 4, {}),
            ],
            9,
        ),
        (
            "kind",
            {},
            [
                _ASSIGNED,
                ("metadata", "{1: 2}", 13, 13, {}),
                ("unknown_metadata", '("kind", {1: 2})', 13, 4, {"name": "kind"}),
            ],
            10,
        ),
        ("unknown", {}, [_ASSIGNED, ("metadata", "7", 14, 4, {})], 11),
        ("unknown", {}, [("container", "int", 16, 14, {"container": "int"})], 12),
    ]


def test_params_keep_their_insertion_order() -> None:
    declarations = extract_annotation_declarations(ast.parse(_SOURCE).body, _SOURCE)

    assert list(declarations[2].params) == ["protocol_expr"]
    assert list(declarations[3].params) == ["protocol", "protocol_expr"]
    assert list(declarations[4].params) == ["name", "annotation"]
    assert list(declarations[5].params) == ["stage", "variable", "variable_explicit"]


def test_single_valued_issue_points_at_its_own_argument() -> None:
    """A non-literal first argument does not shift a later literal's issue."""
    source = '__archtest__: Annotated[None, required_attribute(f(), "n", 4)] = 5\n'

    (declaration,) = extract_annotation_declarations(ast.parse(source).body, source)

    # Only the first argument is the name, so the ``"n"`` after it is surplus.
    assert declaration.params == {}
    assert _summary(declaration)[2][1:] == [
        ("arg", "f()", 1, 49, {"index": 0, "name": "required_attribute"}),
        ("arg", "'n'", 1, 54, {"index": 1, "name": "required_attribute"}),
        ("arg", "4", 1, 59, {"index": 2, "name": "required_attribute"}),
    ]


def _only(marker: str):
    source = f"__archtest__: Annotated[None, {marker}]\n"
    (declaration,) = extract_annotation_declarations(ast.parse(source).body, source)
    return declaration


@pytest.mark.parametrize(
    "marker", ["implements_protocol", "implements_runtime_protocol"]
)
@pytest.mark.parametrize(("surplus", "expr"), [('"x"', "'x'"), ("2", "2")])
def test_a_surplus_argument_of_a_protocol_marker_is_an_issue(
    marker: str, surplus: str, expr: str
) -> None:
    """The protocol is the first argument; a second one is never stored."""
    declaration = _only(f"{marker}(Seller, {surplus})")

    assert declaration.params == {"protocol_expr": "Seller"}
    assert _summary(declaration)[2] == [
        ("arg", expr, 1, 39 + len(marker), {"index": 1, "name": marker})
    ]


@pytest.mark.parametrize(
    "marker", ["implements_protocol(Seller)", "implements_protocol(protocol=Seller)"]
)
def test_a_protocol_given_once_has_no_issue(marker: str) -> None:
    declaration = _only(marker)

    assert declaration.params == {"protocol_expr": "Seller"}
    assert declaration.unsupported == []


def test_a_protocol_keyword_overrides_the_positional_protocol_silently() -> None:
    """Pinned as it is: Python itself would reject the call with a TypeError."""
    declaration = _only("implements_protocol(Seller, protocol=Other)")

    assert declaration.params == {"protocol_expr": "Other"}
    assert declaration.unsupported == []


def test_only_the_first_argument_is_the_value_of_a_single_valued_marker() -> None:
    """A literal after a rejected first argument does not take its place."""
    declaration = _only('required_attribute(f(), "n")')

    assert declaration.params == {}
    assert _summary(declaration)[2] == [
        ("arg", "f()", 1, 49, {"index": 0, "name": "required_attribute"}),
        ("arg", "'n'", 1, 54, {"index": 1, "name": "required_attribute"}),
    ]


@pytest.mark.parametrize("marker", ["required_method", "is_enum"])
def test_a_marker_without_positional_parameters_reports_a_literal_one(
    marker: str,
) -> None:
    declaration = _only(f'{marker}("x", 1)')

    assert declaration.params == {}
    assert _summary(declaration)[2] == [
        ("arg", "'x'", 1, 31 + len(marker), {"index": 0, "name": marker}),
        ("arg", "1", 1, 36 + len(marker), {"index": 1, "name": marker}),
    ]
