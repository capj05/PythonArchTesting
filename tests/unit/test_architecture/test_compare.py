"""Comparing a target's module graph with the reference's (F2)."""

from __future__ import annotations

import pytest

from pythonarchtesting.architecture.compare import (
    EdgeDiff,
    compare_edges,
    compare_packages,
    fold_new_modules,
    parse_edge,
)

_KNOWN = {"c", "s", "r"}
_REFERENCE = {("c", "s"), ("s", "r")}


def _target(*pairs: tuple[str, str]) -> dict[tuple[str, str], int]:
    return {pair: index for index, pair in enumerate(pairs)}


def test_strict_reports_every_extra_edge() -> None:
    diff = compare_edges(
        _REFERENCE,
        _target(("c", "s"), ("s", "r"), ("c", "r")),
        policy="strict",
        known=_KNOWN,
    )

    assert diff.divergent == [("c", "r")]
    assert diff.convergent == [("c", "s"), ("s", "r")]


def test_allow_new_modules_folds_a_helper_into_its_caller() -> None:
    passed = compare_edges(
        {("c", "s")},
        _target(("c", "h"), ("h", "s")),
        policy="allow_new_modules",
        known=_KNOWN,
    )
    bypass = compare_edges(
        {("c", "s")},
        _target(("c", "s"), ("c", "h"), ("h", "r")),
        policy="allow_new_modules",
        known=_KNOWN,
    )

    assert passed.divergent == []
    assert bypass.divergent == [("c", "r")]


def test_strict_does_not_fold() -> None:
    diff = compare_edges(
        {("c", "s")}, _target(("c", "h"), ("h", "s")), policy="strict", known=_KNOWN
    )

    assert diff.divergent == [("c", "h"), ("h", "s")]


def test_layered_flags_only_upward_edges() -> None:
    upward = compare_edges(
        _REFERENCE,
        _target(("c", "s"), ("s", "r"), ("r", "c")),
        policy="layered",
        known=_KNOWN,
    )
    downward = compare_edges(
        _REFERENCE,
        _target(("c", "s"), ("s", "r"), ("c", "r")),
        policy="layered",
        known=_KNOWN,
    )

    assert upward.divergent == [("r", "c")]
    assert downward.divergent == []
    assert downward.undecided == [("c", "r")]


def test_unfoldable_new_modules_are_undecided() -> None:
    diff = compare_edges(
        set(),
        _target(("h1", "h2"), ("h2", "h1"), ("h1", "s")),
        policy="allow_new_modules",
        known={"s"},
    )

    assert diff.divergent == []
    assert diff.undecided == [("h1", "h2"), ("h1", "s"), ("h2", "h1")]


def test_fold_returns_what_it_could_not_fold() -> None:
    folded, dropped = fold_new_modules({("h", "s"): 1, ("c", "s"): 2}, {"c", "s"})

    assert folded == {("c", "s"): 2}
    assert dropped == {("h", "s"): 1}


def test_allow_and_forbid_override_the_reference() -> None:
    diff = compare_edges(
        _REFERENCE,
        _target(("c", "s"), ("s", "r"), ("c", "r")),
        policy="strict",
        known=_KNOWN,
        allow=[("c", "r")],
        forbid=[("c", "s")],
    )

    assert diff.allowed == [("c", "r")]
    assert diff.divergent == [("c", "s")]


def test_absent_lists_reference_edges_the_target_lacks() -> None:
    diff = compare_edges(
        _REFERENCE, _target(("c", "s")), policy="allow_new_modules", known=_KNOWN
    )

    assert diff.absent == [("s", "r")]
    assert diff.divergent == []


def test_packages_new_to_the_reference_diverge() -> None:
    diff = compare_packages(
        {"json"},
        _target(
            ("service", "pickle"), ("controller", "json"), ("service", "__future__")
        ),
        ignore={"__future__"},
    )

    assert diff.divergent == [("service", "pickle")]
    assert diff.convergent == [("controller", "json")]


def test_packages_allow_and_forbid() -> None:
    diff = compare_packages(
        {"json"},
        _target(("service", "pickle"), ("controller", "json")),
        ignore=(),
        allow=[("service", "pickle")],
        forbid=[("controller", "json")],
    )

    assert diff.allowed == [("service", "pickle")]
    assert diff.divergent == [("controller", "json")]


def test_no_external_use_on_either_side_is_clean() -> None:
    diff = compare_packages(
        set(), _target(("service", "__future__")), ignore={"__future__"}
    )

    assert diff == EdgeDiff()


def test_to_dict_renders_sorted_arrows() -> None:
    diff = EdgeDiff(divergent=[("s", "r"), ("c", "r")])

    assert diff.to_dict()["divergent"] == ["c -> r", "s -> r"]
    assert diff.to_dict()["undecided"] == []


@pytest.mark.parametrize("text", ["a->", "a", "-> b", "a -> b -> c", ""])
def test_parse_edge_rejects_malformed(text: str) -> None:
    with pytest.raises(ValueError):
        parse_edge(text)


@pytest.mark.parametrize("text", ["a->b", " a  ->  b ", "a -> b"])
def test_parse_edge_accepts_spacing(text: str) -> None:
    assert parse_edge(text) == ("a", "b")


def test_instances_new_to_the_reference_diverge() -> None:
    from pythonarchtesting.architecture.compare import compare_instances

    diff = compare_instances(
        {("s", "m.Order")},
        _target(("s", "m.Order"), ("s", "r.Repo")),
        policy="allow_new_modules",
        reference_calls=_REFERENCE,
    )

    assert diff.convergent == [("s", "m.Order")]
    assert diff.divergent == [("s", "r.Repo")]


def test_instances_under_layered_flag_only_upward_creation() -> None:
    from pythonarchtesting.architecture.compare import compare_instances

    downward = compare_instances(
        set(), _target(("c", "r.Repo")), policy="layered", reference_calls=_REFERENCE
    )
    upward = compare_instances(
        set(), _target(("r", "c.Ctl")), policy="layered", reference_calls=_REFERENCE
    )

    assert downward.undecided == [("c", "r.Repo")] and downward.divergent == []
    assert upward.divergent == [("r", "c.Ctl")]


def test_instance_exceptions_match_the_class_or_its_module() -> None:
    from pythonarchtesting.architecture.compare import compare_instances

    diff = compare_instances(
        set(),
        _target(("s", "r.Repo"), ("c", "r.Repo")),
        policy="strict",
        reference_calls=_REFERENCE,
        allow=[("s", "r")],
        forbid=[("c", "r.Repo")],
    )

    assert diff.allowed == [("s", "r.Repo")]
    assert diff.divergent == [("c", "r.Repo")]


def test_forbid_wins_over_ignore_for_packages() -> None:
    diff = compare_packages(
        {"json"},
        _target(("service", "typing")),
        ignore={"typing"},
        forbid=[("service", "typing")],
    )

    assert diff.divergent == [("service", "typing")]


def test_an_exception_on_a_package_covers_its_submodules() -> None:
    diff = compare_edges(
        set(),
        _target(("pkg.a", "models"), ("other", "models")),
        policy="strict",
        known={"pkg", "pkg.a", "models", "other"},
        allow=[("pkg", "models")],
    )

    assert diff.allowed == [("pkg.a", "models")]
    assert diff.divergent == [("other", "models")]


def test_the_diff_keeps_the_reference_edges_an_exception_covers():
    from pythonarchtesting.architecture.compare import compare_edges

    diff = compare_edges(
        {("ui", "svc"), ("svc", "repo")},
        {("ui", "svc"): None, ("svc", "repo"): None},
        policy="strict",
        known={"ui", "svc", "repo"},
        allow=[("svc", "repo")],
    ).to_dict()

    assert diff["allowed"] == ["svc -> repo"]
    assert diff["reference"] == ["svc -> repo", "ui -> svc"]


def test_a_nested_class_belongs_to_its_module():
    from pythonarchtesting.architecture.compare import compare_instances

    diff = compare_instances(
        set(),
        {("svc", "models.Outer.Inner"): None},
        policy="strict",
        reference_calls=set(),
        allow=[("svc", "models")],
        modules={"svc", "models"},
    )

    assert diff.allowed == [("svc", "models.Outer.Inner")]
