"""Characterization tests for ``compatible_compare``.

The tests pin the exact error list (texts and order) the function returns
today, so that a refactor of the function can be checked for unchanged
behaviour. They cover both comparison strategies (by position with
``allow_param_rename`` and by name), positional and keyword-only parameters,
fewer/equal/more parameters, kind and annotation agreement, and both values of
``allow_extra_params``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.core.models import EvalContext
from pythonarchtesting.entities import Entity, build_entity_index
from pythonarchtesting.entities_extraction import extract_entities_from_source
from pythonarchtesting.execution.evaluators.signature_comparison import (
    compatible_compare,
)

_MODULE = """
class Base:
    pass

class Child(Base):
    pass

def api():
    return None
"""

_EXTRA_REQUIRED = (
    "extra required parameter(s) {}: "
    "callers of the reference's signature do not pass them"
)
_FEWER_POSITIONAL = "target has fewer positional-compatible parameters than required"
_FEWER_KWONLY = "target has fewer keyword-only parameters than required"


def _entities(role: str) -> list[Entity]:
    return extract_entities_from_source(
        source_text=_MODULE,
        file_path=Path(f"{role}_module.py"),
        root_path=Path("."),
        target_module_name=None,
        role=role,  # type: ignore[arg-type]
        include_nested_functions=False,
        root_label=role,
    )


@pytest.fixture(scope="module")
def setting() -> tuple[Entity, Entity, EvalContext]:
    """Return the source and target function entities and their context.

    Both roles hold the same module, so ``Base``/``Child`` annotations resolve
    to classes and the contravariant annotation check can be observed.
    """
    source_entities = _entities("source")
    target_entities = _entities("target")
    ctx = EvalContext(
        source_index=build_entity_index(source_entities),
        target_index=build_entity_index(target_entities),
        matches={},
        config=None,
        source_by_id={entity.canonical_id: entity for entity in source_entities},
        target_by_id={entity.canonical_id: entity for entity in target_entities},
    )
    source = next(entity for entity in source_entities if entity.name == "api")
    target = next(entity for entity in target_entities if entity.name == "api")
    return source, target, ctx


def _p(
    name: str,
    kind: str = "pos_or_kw",
    *,
    required: bool = True,
    annotation: str | None = None,
) -> dict[str, Any]:
    """Build one parameter in the shape ``param_model`` produces."""
    return {
        "name": name,
        "kind": kind,
        "required": required,
        "annotation": annotation,
    }


def _run(
    setting: tuple[Entity, Entity, EvalContext],
    expected: list[dict[str, Any]],
    found: list[dict[str, Any]],
    *,
    allow_extra_params: bool,
    allow_param_rename: bool,
) -> list[str]:
    source, target, ctx = setting
    return compatible_compare(
        expected,
        found,
        allow_extra_params=allow_extra_params,
        allow_param_rename=allow_param_rename,
        source=source,
        target=target,
        ctx=ctx,
    )


# Each case: (expected params, found params, expected errors). The rename
# branch ignores ``allow_extra_params``, so every case is run with both values.
_RENAME_CASES = [
    pytest.param([], [], [], id="empty"),
    pytest.param(
        [_p("a", annotation="int"), _p("k", "kwonly", annotation="str")],
        [_p("x", annotation="int"), _p("y", "kwonly", annotation="str")],
        [],
        id="same-count-renamed-all-agree",
    ),
    pytest.param(
        [_p("a"), _p("b")],
        [_p("a")],
        [_FEWER_POSITIONAL],
        id="positional-fewer",
    ),
    pytest.param(
        [_p("a", "posonly", annotation="int"), _p("b")],
        [_p("a", "pos_or_kw", annotation="str")],
        [_FEWER_POSITIONAL],
        id="positional-fewer-skips-pairwise-checks",
    ),
    pytest.param(
        [_p("k", "kwonly"), _p("m", "kwonly")],
        [_p("k", "kwonly")],
        [_FEWER_KWONLY],
        id="kwonly-fewer",
    ),
    pytest.param(
        [_p("a"), _p("k", "kwonly")],
        [],
        [_FEWER_POSITIONAL, _FEWER_KWONLY],
        id="both-fewer-positional-first",
    ),
    pytest.param(
        [_p("a", annotation="int"), _p("k", "kwonly", annotation="int")],
        [_p("k", "kwonly", annotation="str")],
        [
            _FEWER_POSITIONAL,
            "parameter annotation mismatch: expected int, found str",
        ],
        id="positional-fewer-kwonly-still-compared",
    ),
    pytest.param(
        [_p("a", annotation="int")],
        [_p("a", "kwonly", annotation="int")],
        [_FEWER_POSITIONAL],
        id="positional-moved-to-kwonly-counts-as-fewer",
    ),
    pytest.param(
        [_p("a", "posonly")],
        [_p("a", "pos_or_kw")],
        ["parameter kind mismatch: expected posonly, found pos_or_kw"],
        id="positional-kind-mismatch",
    ),
    pytest.param(
        [_p("a", annotation="int")],
        [_p("b", annotation="str")],
        ["parameter annotation mismatch: expected int, found str"],
        id="positional-annotation-mismatch-no-name-in-text",
    ),
    pytest.param(
        [_p("a", "posonly", annotation="int")],
        [_p("a", "pos_or_kw", annotation="str")],
        [
            "parameter kind mismatch: expected posonly, found pos_or_kw",
            "parameter annotation mismatch: expected int, found str",
        ],
        id="positional-kind-then-annotation",
    ),
    pytest.param(
        [_p("a", annotation="int")],
        [_p("a")],
        ["parameter annotation mismatch: expected int, found None"],
        id="positional-annotation-missing-on-target",
    ),
    pytest.param(
        [_p("a")],
        [_p("a", annotation="int")],
        [],
        id="positional-annotation-only-on-target",
    ),
    pytest.param(
        [_p("a", annotation="Child")],
        [_p("a", annotation="Base")],
        [],
        id="positional-annotation-contravariant-widening-ok",
    ),
    pytest.param(
        [_p("a", annotation="Base")],
        [_p("a", annotation="Child")],
        [
            "parameter annotation mismatch: "
            "expected source_module.Base, found target_module.Child"
        ],
        id="positional-annotation-contravariant-narrowing",
    ),
    pytest.param(
        [_p("k", "kwonly", annotation="int")],
        [_p("z", "kwonly", annotation="str")],
        ["parameter annotation mismatch: expected int, found str"],
        id="kwonly-annotation-mismatch-no-name-in-text",
    ),
    pytest.param(
        [_p("a", required=False)],
        [_p("a", required=True)],
        [],
        id="optional-to-required-ignored",
    ),
    pytest.param(
        [_p("a", annotation="int"), _p("b")],
        [_p("a", annotation="int"), _p("b"), _p("c", annotation="str")],
        [],
        id="positional-more-required-extra-ignored",
    ),
    pytest.param(
        [_p("k", "kwonly")],
        [_p("k", "kwonly"), _p("extra", "kwonly")],
        [],
        id="kwonly-more-required-extra-ignored",
    ),
    pytest.param(
        [
            _p("a", "posonly"),
            _p("b", annotation="int"),
            _p("k", "kwonly", annotation="int"),
            _p("m", "kwonly", annotation="str"),
        ],
        [
            _p("a", "pos_or_kw"),
            _p("b", annotation="str"),
            _p("k", "kwonly", annotation="str"),
            _p("m", "kwonly", annotation="int"),
        ],
        [
            "parameter kind mismatch: expected posonly, found pos_or_kw",
            "parameter annotation mismatch: expected int, found str",
            "parameter annotation mismatch: expected int, found str",
            "parameter annotation mismatch: expected str, found int",
        ],
        id="errors-in-parameter-order-positional-before-kwonly",
    ),
    pytest.param(
        [_p("k", "kwonly"), _p("a", annotation="int")],
        [_p("a", annotation="str"), _p("k", "kwonly")],
        ["parameter annotation mismatch: expected int, found str"],
        id="kwonly-pairing-independent-of-declaration-order",
    ),
]


@pytest.mark.parametrize("allow_extra_params", [True, False])
@pytest.mark.parametrize(("expected", "found", "errors"), _RENAME_CASES)
def test_rename_branch_pins_current_errors(
    setting: tuple[Entity, Entity, EvalContext],
    expected: list[dict[str, Any]],
    found: list[dict[str, Any]],
    errors: list[str],
    allow_extra_params: bool,
) -> None:
    """The rename branch compares by position and returns early.

    Pinned current behaviour (a probable defect, left for the owner to
    decide): the rename branch returns before the extra-parameter check, so
    ``allow_extra_params=False`` has no effect here and required extra
    parameters on the target are not reported either. The same expected
    list is therefore asserted for both values of ``allow_extra_params``.
    """
    assert (
        _run(
            setting,
            expected,
            found,
            allow_extra_params=allow_extra_params,
            allow_param_rename=True,
        )
        == errors
    )


# Each case: (expected params, found params, errors with extras allowed,
# errors with extras forbidden).
_BY_NAME_CASES = [
    pytest.param([], [], [], [], id="empty"),
    pytest.param(
        [_p("a", annotation="int"), _p("k", "kwonly", annotation="str")],
        [_p("k", "kwonly", annotation="str"), _p("a", annotation="int")],
        [],
        [],
        id="same-params-any-order",
    ),
    pytest.param(
        [_p("a"), _p("b")],
        [_p("a")],
        ["missing parameter 'b'"],
        ["missing parameter 'b'"],
        id="positional-fewer",
    ),
    pytest.param(
        [_p("k", "kwonly"), _p("m", "kwonly", annotation="int")],
        [_p("k", "kwonly")],
        ["missing parameter 'm'"],
        ["missing parameter 'm'"],
        id="kwonly-fewer",
    ),
    pytest.param(
        [_p("a")],
        [_p("a", "kwonly")],
        ["parameter kind mismatch for 'a': expected pos_or_kw, found kwonly"],
        ["parameter kind mismatch for 'a': expected pos_or_kw, found kwonly"],
        id="kind-mismatch",
    ),
    pytest.param(
        [_p("a", required=False)],
        [_p("a", required=True)],
        ["optional parameter became required: 'a'"],
        ["optional parameter became required: 'a'"],
        id="optional-became-required",
    ),
    pytest.param(
        [_p("a", required=True)],
        [_p("a", required=False)],
        [],
        [],
        id="required-became-optional-ok",
    ),
    pytest.param(
        [_p("a", annotation="int")],
        [_p("a", annotation="str")],
        ["parameter annotation mismatch for 'a': expected int, found str"],
        ["parameter annotation mismatch for 'a': expected int, found str"],
        id="positional-annotation-mismatch",
    ),
    pytest.param(
        [_p("k", "kwonly", annotation="int")],
        [_p("k", "kwonly")],
        ["parameter annotation mismatch for 'k': expected int, found None"],
        ["parameter annotation mismatch for 'k': expected int, found None"],
        id="kwonly-annotation-missing-on-target",
    ),
    pytest.param(
        [_p("a")],
        [_p("a", annotation="int")],
        [],
        [],
        id="annotation-only-on-target",
    ),
    pytest.param(
        [_p("a", annotation="Child")],
        [_p("a", annotation="Base")],
        [],
        [],
        id="annotation-contravariant-widening-ok",
    ),
    pytest.param(
        [_p("a", annotation="Base")],
        [_p("a", annotation="Child")],
        [
            "parameter annotation mismatch for 'a': "
            "expected source_module.Base, found target_module.Child"
        ],
        [
            "parameter annotation mismatch for 'a': "
            "expected source_module.Base, found target_module.Child"
        ],
        id="annotation-contravariant-narrowing",
    ),
    pytest.param(
        [_p("a", "posonly", required=False, annotation="int")],
        [_p("a", "pos_or_kw", required=True, annotation="str")],
        [
            "parameter kind mismatch for 'a': expected posonly, found pos_or_kw",
            "optional parameter became required: 'a'",
            "parameter annotation mismatch for 'a': expected int, found str",
        ],
        [
            "parameter kind mismatch for 'a': expected posonly, found pos_or_kw",
            "optional parameter became required: 'a'",
            "parameter annotation mismatch for 'a': expected int, found str",
        ],
        id="kind-then-required-then-annotation",
    ),
    pytest.param(
        [_p("b", annotation="int"), _p("a"), _p("c", required=False)],
        [_p("c"), _p("b", annotation="str")],
        [
            "parameter annotation mismatch for 'b': expected int, found str",
            "missing parameter 'a'",
            "optional parameter became required: 'c'",
        ],
        [
            "parameter annotation mismatch for 'b': expected int, found str",
            "missing parameter 'a'",
            "optional parameter became required: 'c'",
        ],
        id="errors-in-expected-order",
    ),
    pytest.param(
        [_p("a")],
        [_p("a"), _p("z", required=False)],
        [],
        ["extra parameters not allowed: z"],
        id="more-optional-extra",
    ),
    pytest.param(
        [_p("a")],
        [_p("a"), _p("z", "kwonly")],
        [_EXTRA_REQUIRED.format("z")],
        ["extra parameters not allowed: z"],
        id="more-required-kwonly-extra",
    ),
    pytest.param(
        [_p("a")],
        [_p("z"), _p("a"), _p("m", required=False), _p("b", "kwonly")],
        [_EXTRA_REQUIRED.format("b, z")],
        ["extra parameters not allowed: b, m, z"],
        id="more-extras-sorted-only-required-reported-when-allowed",
    ),
    pytest.param(
        [_p("a", annotation="int")],
        [_p("b", annotation="int")],
        ["missing parameter 'a'", _EXTRA_REQUIRED.format("b")],
        ["missing parameter 'a'", "extra parameters not allowed: b"],
        id="renamed-is-missing-plus-extra",
    ),
    pytest.param(
        [_p("a"), _p("b")],
        [_p("a"), _p("x", required=False)],
        ["missing parameter 'b'"],
        ["missing parameter 'b'", "extra parameters not allowed: x"],
        id="same-count-one-renamed-optional",
    ),
    pytest.param(
        [_p("a")],
        [_p("a", "posonly"), _p("a", "pos_or_kw")],
        [],
        [],
        id="duplicate-target-name-last-wins",
    ),
    pytest.param(
        [{"kind": "pos_or_kw", "required": True, "annotation": None}],
        [{"kind": "pos_or_kw", "required": True, "annotation": None}],
        [],
        [],
        id="nameless-params-match-as-None",
    ),
    pytest.param(
        [{"kind": "pos_or_kw", "required": True, "annotation": None}],
        [],
        ["missing parameter 'None'"],
        ["missing parameter 'None'"],
        id="nameless-param-missing-as-None",
    ),
]


@pytest.mark.parametrize(
    ("expected", "found", "errors_allowed", "errors_forbidden"), _BY_NAME_CASES
)
@pytest.mark.parametrize("allow_extra_params", [True, False])
def test_by_name_branch_pins_current_errors(
    setting: tuple[Entity, Entity, EvalContext],
    expected: list[dict[str, Any]],
    found: list[dict[str, Any]],
    errors_allowed: list[str],
    errors_forbidden: list[str],
    allow_extra_params: bool,
) -> None:
    """The by-name branch pairs parameters by name and then checks extras."""
    assert _run(
        setting,
        expected,
        found,
        allow_extra_params=allow_extra_params,
        allow_param_rename=False,
    ) == (errors_allowed if allow_extra_params else errors_forbidden)


def test_inputs_are_not_mutated(
    setting: tuple[Entity, Entity, EvalContext],
) -> None:
    """Neither branch may change the parameter lists it is given."""
    expected = [_p("a", annotation="int"), _p("k", "kwonly")]
    found = [_p("b", annotation="str"), _p("z", "kwonly"), _p("q")]
    snapshot = ([dict(p) for p in expected], [dict(p) for p in found])
    for rename in (True, False):
        for extra in (True, False):
            _run(
                setting,
                expected,
                found,
                allow_extra_params=extra,
                allow_param_rename=rename,
            )
    assert (expected, found) == snapshot
