"""An invalid logical or enumerated argument makes a declaration invalid.

A logical argument (one the marker helper types ``bool``) accepts only
``True`` and ``False``; ``None`` stands for its default. Any other value
(``"no"``, ``"false"``, ``1``, ``0``) is not read for its truthiness but drops
the declaration: the marker's compiler returns a ``compiler_invalid_param``
sentinel rule for the argument, with the valid values ``[True, False]``, and
compiler evidence with the issue ``invalid_<argument>``, through the same
sentinel and evidence the marker reports an invalid severity with.

An enumerated argument accepts only its listed values (in any case where the
marker reads them so); ``None`` stands for its default. Any other value drops
the declaration instead of being replaced by the default. The arguments
whose values the compiler already checked keep how they report an invalid
value (:data:`_KEPT`); the others report it as a logical argument does.

Each case compiles a small package declaring the one marker once.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from pythonarchtesting.config.loader import load_config
from pythonarchtesting.rules.compilation import compile_rules
from pythonarchtesting.rules.declaration import core as declaration_helpers
from pythonarchtesting.runner.source_prep import prepare_source

_INIT = """
from typing import Annotated

from pythonarchtesting.rules import architecture_entry, enforce_layers, forbid_cycles

INIT
"""

_MODELS = """
class Record:
    pass
"""

_APP = """
from __future__ import annotations

from typing import Annotated, Protocol

from pythonarchtesting.rules import MARKER

MODULE


class Port(Protocol):
    def run(self) -> None: ...


class Base:
    pass


class Service(Base):
    CLASS

    def __new__(cls, value: int) -> Service:
        return super().__new__(cls)

    def __init__(self, value: int) -> None:
        self.value = value

    @classmethod
    def create(cls) -> Service:
        FACTORY
        return cls(1)

    def run(self) -> None:
        METHOD


def handler(value: int) -> int:
    FUNCTION
    return value
"""

_SITES = ("INIT", "MODULE", "CLASS", "FACTORY", "METHOD", "FUNCTION")

_CASES = '[{"args": [1]}]'

# marker -> (where it is declared, the arguments a valid declaration needs)
_DECLARED: dict[str, tuple[str, str]] = {
    "architecture_entry": ("INIT", f'entry="app.handler", cases={_CASES}'),
    "does_not_have": ("CLASS", '"secret"'),
    "enforce_layers": ("INIT", '"app", "models"'),
    "enforce_reference_calls": ("FUNCTION", f"cases={_CASES}"),
    "forbid_cycles": ("INIT", ""),
    "forbid_imports": ("MODULE", '"requests"'),
    "forbid_runtime_calls": ("FUNCTION", f'"models", cases={_CASES}'),
    "forbid_runtime_instantiation": ("FUNCTION", f'"models", cases={_CASES}'),
    "implements_protocol": ("CLASS", "Port"),
    "module_interface": ("MODULE", '"Service"'),
    "require_member_set": ("CLASS", ""),
    "require_method_set": ("CLASS", ""),
    "required_attribute": ("CLASS", '"value"'),
    "required_constructor": ("CLASS", ""),
    "required_entity_signature": ("FUNCTION", ""),
    "required_factory": ("FACTORY", ""),
    "required_method": ("METHOD", ""),
}


class Choice(NamedTuple):
    """The valid values of an enumerated argument, whether the compiler reads
    them in any case, and the arguments some value needs besides."""

    values: tuple[Any, ...]
    any_case: bool = True
    needs: dict[Any, str] = {}
    site: str | None = None


_MEMBER_KINDS = ("any", "method", "attribute", "property", "descriptor", "constructor")

# (marker, argument) -> its valid values
_CHOICES: dict[tuple[str, str], Choice] = {
    ("architecture_entry", "policy"): Choice(
        ("allow_new_modules", "strict", "layered"), any_case=False
    ),
    ("does_not_have", "member_kind"): Choice(
        ("any", "method", "attribute", "property")
    ),
    ("does_not_have", "storage"): Choice(("any", "instance", "class")),
    ("does_not_have", "name_match"): Choice(
        ("exact", "alias", "regex"),
        needs={"alias": 'aliases=["secret"]', "regex": 'pattern="secret"'},
    ),
    ("does_not_have", "signature_mode"): Choice(
        ("any", "compatible", "exact"), site="METHOD"
    ),
    ("forbid_imports", "scope"): Choice(("package", "module", "entity")),
    ("forbid_imports", "mode"): Choice(("reachable", "direct"), any_case=False),
    ("implements_protocol", "signature_mode"): Choice(("compatible", "exact", "any")),
    ("implements_protocol", "return_annotation"): Choice(("off", "warning", "error")),
    ("require_member_set", "member_kinds"): Choice(
        tuple((kind,) for kind in _MEMBER_KINDS)
    ),
    ("require_member_set", "name_match"): Choice(
        ("any", "regex", "names"),
        needs={"regex": 'pattern="run"', "names": 'names=["run"]'},
    ),
    ("require_member_set", "method_kind"): Choice(
        ("any", "instance", "classmethod", "staticmethod")
    ),
    ("require_member_set", "storage"): Choice(("any", "instance", "class")),
    ("require_member_set", "descriptor_kinds"): Choice(
        (("cached_property",), ("classproperty",))
    ),
    ("require_member_set", "constructor_kind"): Choice(
        ("auto", "__init__", "__new__"), any_case=False
    ),
    ("require_method_set", "name_match"): Choice(
        ("any", "regex", "names"),
        needs={"regex": 'pattern="run"', "names": 'names=["run"]'},
    ),
    ("require_method_set", "method_kind"): Choice(
        ("any", "instance", "classmethod", "staticmethod")
    ),
    ("required_attribute", "storage"): Choice(("any", "instance", "class")),
    ("required_attribute", "descriptor_kinds"): Choice(
        (("cached_property",), ("classproperty",))
    ),
    ("required_constructor", "signature_mode"): Choice(("compatible", "exact", "any")),
    ("required_constructor", "constructor_kind"): Choice(
        ("auto", "__init__", "__new__")
    ),
    ("required_entity_signature", "mode"): Choice(("compatible", "exact", "any")),
    ("required_entity_signature", "return_annotation"): Choice(
        ("off", "ignore", "warning", "error")
    ),
    ("required_factory", "signature_mode"): Choice(("compatible", "exact", "any")),
    ("required_factory", "satisfy_with"): Choice(
        (
            ("constructor",),
            ("classmethod",),
            ("staticmethod",),
            ("static_attribute",),
        ),
        needs={("static_attribute",): 'name_match="exact"'},
    ),
    ("required_factory", "name_match"): Choice(
        ("any", "exact", "alias", "regex"),
        needs={"alias": 'aliases=["create"]', "regex": 'pattern="create"'},
    ),
    ("required_factory", "return_annotation_mode"): Choice(
        ("ignore", "compatible", "exact")
    ),
    ("required_factory", "detection_mode"): Choice(("strict", "extended")),
    ("required_method", "signature_mode"): Choice(("compatible", "exact", "any")),
    ("required_method", "name_match"): Choice(
        ("exact", "alias", "regex", "any"),
        needs={"alias": 'aliases=["run"]', "regex": 'pattern="run"'},
    ),
}

# Enumerated arguments the compiler already refused an invalid value of:
# they keep the sentinel and evidence they have always reported it with.
_KEPT = {
    ("architecture_entry", "policy"),
    ("forbid_imports", "mode"),
    ("require_member_set", "member_kinds"),
    ("require_member_set", "name_match"),
    ("require_member_set", "method_kind"),
    ("require_member_set", "storage"),
    ("require_member_set", "descriptor_kinds"),
    ("require_member_set", "constructor_kind"),
    ("require_method_set", "name_match"),
    ("require_method_set", "method_kind"),
    ("required_attribute", "storage"),
    ("required_attribute", "descriptor_kinds"),
    ("required_constructor", "signature_mode"),
    ("required_constructor", "constructor_kind"),
    ("required_entity_signature", "return_annotation"),
    ("required_factory", "signature_mode"),
    ("required_factory", "satisfy_with"),
    ("required_factory", "return_annotation_mode"),
    ("required_factory", "detection_mode"),
    ("required_method", "name_match"),
}

# Text-valued arguments that name things rather than pick one of a few values.
_FREE_TEXT = {
    "access",
    "aliases",
    "allow",
    "annotation",
    "base",
    "cases",
    "closed",
    "entry",
    "forbid",
    "forbidden",
    "ignore_external",
    "ignore_globs",
    "init",
    "layers",
    "member",
    "modules",
    "name",
    "names",
    "notify",
    "package",
    "pattern",
    "spy",
    "stage",
    "stages",
    "subscribe",
    "through",
    "types",
    "unsubscribe",
    "variable",
}

_INVALID_BOOLS = ("no", "false", 1, 0)
_VALID_BOOLS = (True, False, None)


def _helpers() -> dict[str, inspect.Signature]:
    return {
        name: inspect.signature(helper)
        for name, helper in inspect.getmembers(declaration_helpers, inspect.isfunction)
        if not name.startswith("_")
    }


def _bool_params() -> list[tuple[str, str]]:
    """Every (marker, argument) whose helper types the argument ``bool``."""
    return sorted(
        (name, param.name)
        for name, signature in _helpers().items()
        for param in signature.parameters.values()
        if param.annotation in ("bool", bool)
    )


def _text_params() -> set[tuple[str, str]]:
    """Every (marker, argument) whose helper types the argument as text."""
    return {
        (name, param.name)
        for name, signature in _helpers().items()
        for param in signature.parameters.values()
        if "str" in str(param.annotation) and param.name not in {"severity", "message"}
    }


def _default(marker: str, param: str) -> Any:
    return _helpers()[marker].parameters[param].default


BOOLS = _bool_params()


def _declaration(marker: str, extra: str, site: str | None = None) -> dict[str, str]:
    """The text of each site of the package: ``marker`` declared at its site
    with its required arguments and ``extra``, every other site empty."""
    default_site, required = _DECLARED[marker]
    arguments = ", ".join(part for part in (required, extra) if part)
    line = f"__archtest__: Annotated[None, {marker}({arguments})]"
    chosen = site or default_site
    return {name: line if name == chosen else "pass" for name in _SITES}


def compile_case(
    tmp_path: Path, marker: str, extra: str, site: str | None = None
) -> tuple[list[Any], list[Any]]:
    """The rules and compiler evidence of a package declaring ``marker`` once."""
    root = tmp_path / "pkg"
    root.mkdir()
    sites = _declaration(marker, extra, site)
    app = _APP.replace("MARKER", marker)
    init = _INIT
    for name, text in sites.items():
        app = app.replace(name, text)
        init = init.replace(name, text)
    for name, text in (("__init__.py", init), ("models.py", _MODELS), ("app.py", app)):
        (root / name).write_text(text, encoding="utf-8")
    config = load_config()
    state = prepare_source(config=config, source_path=root)
    rules, evidence, _ = compile_rules(list(state.source_entities), config)
    return rules, evidence


def _assert_dropped(
    rules: list[Any],
    evidence: list[Any],
    marker: str,
    param: str,
    value: Any,
    valid: list[Any],
) -> None:
    """The declaration gave only a sentinel for ``param`` and evidence with
    the issue ``invalid_<param>``."""
    assert rules, f"{marker}({param}={value!r}) compiled to nothing"
    assert {rule.rule_type for rule in rules} == {"compiler_invalid_param"}
    for sentinel in rules:
        assert sentinel.name == marker
        assert sentinel.rule_id.endswith(f"/{param}")
        assert sentinel.params["param"] == param
        assert sentinel.params["value"] == value
        assert sentinel.params["valid"] == valid
    issues = [item.payload.get("issue") for item in evidence]
    assert issues == [f"invalid_{param}"]


def _assert_compiled(rules: list[Any], evidence: list[Any], marker: str) -> None:
    compiled = [rule for rule in rules if rule.name.startswith(marker)]
    assert compiled
    assert "compiler_invalid_param" not in {rule.rule_type for rule in compiled}
    assert [item.payload for item in evidence if item.payload.get("issue")] == []


def _literal(value: Any) -> str:
    return repr(value)


def test_every_logical_argument_is_declared_somewhere() -> None:
    assert {marker for marker, _ in BOOLS} <= set(_DECLARED)


def test_every_text_argument_is_an_enumeration_or_free_text() -> None:
    """A new text argument must be listed: as an enumeration with its valid
    values, or as free text."""
    unlisted = {
        (marker, param)
        for marker, param in _text_params()
        if param not in _FREE_TEXT and (marker, param) not in _CHOICES
    }

    assert unlisted == set()
    assert _KEPT <= set(_CHOICES)


@pytest.mark.parametrize("value", _INVALID_BOOLS, ids=_literal)
@pytest.mark.parametrize(("marker", "param"), BOOLS)
def test_a_logical_argument_that_is_no_bool_drops_the_declaration(
    tmp_path: Path, marker: str, param: str, value: Any
) -> None:
    rules, evidence = compile_case(tmp_path, marker, f"{param}={value!r}")

    _assert_dropped(rules, evidence, marker, param, value, [True, False])
    sentinel = rules[0]
    assert sentinel.params["compiler_reason"] == f"{param} must be True or False"


@pytest.mark.parametrize("value", _VALID_BOOLS, ids=_literal)
@pytest.mark.parametrize(("marker", "param"), BOOLS)
def test_a_logical_argument_takes_true_false_or_none(
    tmp_path: Path, marker: str, param: str, value: Any
) -> None:
    """``None`` is the default; a compiled rule that carries the argument
    carries the value it stands for."""
    rules, evidence = compile_case(tmp_path, marker, f"{param}={value!r}")

    _assert_compiled(rules, evidence, marker)
    expected = _default(marker, param) if value is None else value
    for rule in rules:
        if param in rule.params:
            assert rule.params[param] is expected, rule.rule_id


def _invalid_choices() -> list[tuple[str, str, Any]]:
    cases: list[tuple[str, str, Any]] = []
    for (marker, param), choice in sorted(_CHOICES.items()):
        tuple_valued = isinstance(choice.values[0], tuple)
        cases.append((marker, param, ("bogus",) if tuple_valued else "bogus"))
    return cases


def _valid_choices() -> list[tuple[str, str, Any]]:
    cases: list[tuple[str, str, Any]] = []
    for (marker, param), choice in sorted(_CHOICES.items()):
        for value in choice.values:
            cases.append((marker, param, value))
            if choice.any_case and isinstance(value, str) and value.title() != value:
                cases.append((marker, param, value.title()))
        cases.append((marker, param, None))
    return cases


def _choice_extra(marker: str, param: str, value: Any) -> str:
    choice = _CHOICES[(marker, param)]
    key = value.lower() if isinstance(value, str) else value
    needs = choice.needs.get(key, "")
    return ", ".join(part for part in (f"{param}={value!r}", needs) if part)


@pytest.mark.parametrize(("marker", "param", "value"), _invalid_choices())
def test_an_invalid_enumerated_argument_drops_the_declaration(
    tmp_path: Path, marker: str, param: str, value: Any
) -> None:
    choice = _CHOICES[(marker, param)]
    rules, evidence = compile_case(
        tmp_path, marker, _choice_extra(marker, param, value), choice.site
    )

    compiled = [rule for rule in rules if rule.name.startswith(marker)]
    assert {rule.rule_type for rule in compiled} <= {"compiler_invalid_param"}
    assert evidence
    if (marker, param) in _KEPT:
        return
    _assert_dropped(compiled, evidence, marker, param, value, sorted(choice.values))


@pytest.mark.parametrize(("marker", "param", "value"), _valid_choices())
def test_each_valid_enumerated_value_compiles(
    tmp_path: Path, marker: str, param: str, value: Any
) -> None:
    choice = _CHOICES[(marker, param)]
    rules, evidence = compile_case(
        tmp_path, marker, _choice_extra(marker, param, value), choice.site
    )

    _assert_compiled(rules, evidence, marker)
