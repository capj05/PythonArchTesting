"""An invalid ``severity`` makes the declaration of every marker invalid.

Every marker that takes ``severity`` accepts only ``"error"``, ``"warning"``
and ``"info"`` (in any case); ``None`` stands for the default ``"error"``.
Any other value drops the declaration: the marker's compiler returns a
``compiler_invalid_param`` sentinel rule for the parameter ``severity`` and
compiler evidence with the issue ``invalid_severity``, through the same
sentinel and evidence the marker reports its other invalid parameters with.

One package declares every marker once, each with a declaration that is
valid apart from the severity; the control run with a valid severity shows
that each one compiles to its rules.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from pythonarchtesting.config.loader import load_config
from pythonarchtesting.rules.compilation import compile_rules
from pythonarchtesting.rules.declaration import core as declaration_helpers
from pythonarchtesting.runner.source_prep import prepare_source

_VALID = ["error", "warning", "info"]
_REASON = "severity must be one of: error, warning, info"

_INIT = """
from typing import Annotated

from pythonarchtesting.rules import architecture_entry, enforce_layers, forbid_cycles

__archtest__: Annotated[
    None,
    architecture_entry(severity=SEV),
    enforce_layers("app", "models", severity=SEV),
    forbid_cycles(severity=SEV),
]
"""

_MODELS = """
class Record:
    pass
"""

_APP = """
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Annotated, Protocol, final

from pythonarchtesting.rules import (
    does_not_have,
    enforce_flow,
    enforce_reference_calls,
    enforce_runtime_observer,
    exact_type,
    flow,
    forbid_foreign_writes,
    forbid_imports,
    forbid_private_access,
    forbid_runtime_calls,
    forbid_runtime_imports,
    forbid_runtime_instantiation,
    forbid_runtime_members,
    implements_protocol,
    implements_runtime_protocol,
    inherits_directly_from,
    is_abstract_class,
    is_abstract_method,
    is_concrete_class,
    is_enum,
    is_final_class,
    is_final_method,
    is_non_abstract_method,
    is_non_final_class,
    is_non_final_method,
    is_runtime_abstract_class,
    is_runtime_concrete_class,
    is_runtime_singleton,
    module_interface,
    not_subclass_of,
    require_member_set,
    require_method_set,
    require_runtime_calls,
    require_runtime_delegation,
    require_runtime_members,
    required_attribute,
    required_constructor,
    required_entity_signature,
    required_factory,
    required_method,
    subclass_of,
)

__archtest__: Annotated[
    None,
    forbid_imports("requests", severity=SEV),
    module_interface("Service", severity=SEV),
    forbid_runtime_imports("sqlite3", severity=SEV),
]


class Port(Protocol):
    def run(self) -> None: ...


class Base:
    pass


class Service(Base):
    __archtest__: Annotated[
        None,
        does_not_have("secret", severity=SEV),
        required_attribute("value", severity=SEV),
        require_method_set(name_match="names", names=["run"], severity=SEV),
        require_member_set(member_kinds=("method",), min_count=1, severity=SEV),
        required_constructor(severity=SEV),
        subclass_of(base="Base", severity=SEV),
        exact_type(base="Service", severity=SEV),
        not_subclass_of(base="Port", severity=SEV),
        inherits_directly_from(base="Base", severity=SEV),
        implements_protocol(Port, severity=SEV),
        is_enum(severity=SEV),
        is_concrete_class(severity=SEV),
        is_final_class(severity=SEV),
        is_non_final_class(severity=SEV),
        is_abstract_class(severity=SEV),
        require_runtime_members("value", cases=[{"args": [1]}], severity=SEV),
        forbid_runtime_members("password", cases=[{"args": [1]}], severity=SEV),
        is_runtime_concrete_class(cases=[{"args": [1]}], severity=SEV),
        is_runtime_abstract_class(severity=SEV),
        implements_runtime_protocol(Port, cases=[{"args": [1]}], severity=SEV),
        is_runtime_singleton(access="instance", cases=[{"args": [1]}], severity=SEV),
        enforce_runtime_observer(
            subscribe="subscribe",
            notify="publish",
            unsubscribe="unsubscribe",
            notify_args=["event"],
            cases=[{"args": [1]}],
            severity=SEV,
        ),
    ]

    def __init__(self, value: int, strategy: object = None) -> None:
        self.value = value
        self.strategy = strategy

    @classmethod
    def create(cls) -> Service:
        __archtest__: Annotated[None, required_factory(severity=SEV)]
        return cls(1)

    def run(self) -> None:
        __archtest__: Annotated[
            None,
            required_method(severity=SEV),
            is_abstract_method(severity=SEV),
            is_non_abstract_method(severity=SEV),
            is_final_method(severity=SEV),
            is_non_final_method(severity=SEV),
        ]

    def apply(self) -> None:
        __archtest__: Annotated[
            None,
            require_runtime_delegation(
                "strategy",
                member="apply",
                init={"args": [1, {"$spy": "strategy"}]},
                cases=[{"args": []}],
                severity=SEV,
            ),
        ]

    def subscribe(self, listener: object) -> None:
        pass

    def unsubscribe(self, listener: object) -> None:
        pass

    def publish(self, event: object) -> None:
        pass


def handler(value: int) -> int:
    __archtest__: Annotated[
        None,
        required_entity_signature(severity=SEV),
        forbid_private_access(severity=SEV),
        forbid_runtime_calls("models", cases=[{"args": [1]}], severity=SEV),
        require_runtime_calls("models", cases=[{"args": [1]}], severity=SEV),
        forbid_runtime_instantiation("models", cases=[{"args": [1]}], severity=SEV),
        enforce_reference_calls(cases=[{"args": [1]}], severity=SEV),
        forbid_foreign_writes(cases=[{"args": [1]}], severity=SEV),
    ]
    return value


def process(value: str) -> str:
    value = value.strip()
    __archtest__: Annotated[None, flow("raw", variable="value")]
    value = value.lower()
    __archtest__: Annotated[None, flow("normalized", variable="value")]
    __archtest__: Annotated[
        None, enforce_flow(["raw", "normalized"], variable="value", severity=SEV)
    ]
    return value


def process_cases(value: str) -> str:
    value = value.strip()
    __archtest__: Annotated[None, flow("raw", variable="value")]
    value = value.lower()
    __archtest__: Annotated[None, flow("normalized", variable="value")]
    __archtest__: Annotated[
        None,
        enforce_flow(
            ["raw", "normalized"],
            variable="value",
            cases=[{"args": [" A "]}],
            severity=SEV,
        ),
    ]
    return value
"""


def _markers_with_severity() -> set[str]:
    """Every marker helper whose signature takes ``severity``."""
    return {
        name
        for name, helper in inspect.getmembers(declaration_helpers, inspect.isfunction)
        if not name.startswith("_")
        and "severity" in inspect.signature(helper).parameters
    }


def compile_package(tmp_path: Path, severity: str) -> tuple[list[Any], list[Any]]:
    """The rules and compiler evidence of the package, every marker declared
    with ``severity`` (Python source text, e.g. ``'"warning"'``)."""
    root = tmp_path / "pkg"
    root.mkdir()
    for name, text in (
        ("__init__.py", _INIT),
        ("models.py", _MODELS),
        ("app.py", _APP),
    ):
        (root / name).write_text(text.replace("SEV", severity), encoding="utf-8")
    config = load_config()
    state = prepare_source(config=config, source_path=root)
    rules, evidence, _ = compile_rules(list(state.source_entities), config)
    return rules, evidence


# Each marker is declared once, except enforce_flow: once statically and once
# with cases, which compiles through its own runtime path.
_DECLARATIONS = {"enforce_flow": 2}
# A sibling rule a declaration adds whose severity is not the marker's.
_SIBLINGS = {"required_entity_signature_return"}
MARKERS = sorted(_markers_with_severity())


@pytest.fixture(scope="module")
def control(tmp_path_factory: pytest.TempPathFactory) -> tuple[list[Any], list[Any]]:
    return compile_package(tmp_path_factory.mktemp("control"), '"Warning"')


@pytest.fixture(scope="module")
def invalid(tmp_path_factory: pytest.TempPathFactory) -> tuple[list[Any], list[Any]]:
    return compile_package(tmp_path_factory.mktemp("invalid"), '"fatal"')


def _evidence_of(evidence: list[Any], marker: str) -> list[Any]:
    """The compiler evidence about declarations of ``marker``."""
    return [
        item
        for item in evidence
        if item.payload.get("decorator", item.payload.get("declaration")) == marker
    ]


def test_the_package_declares_every_marker_that_takes_a_severity(
    control: tuple[list[Any], list[Any]],
) -> None:
    rules, _ = control

    assert {rule.name for rule in rules} - _SIBLINGS == set(MARKERS)


@pytest.mark.parametrize("marker", MARKERS)
def test_a_valid_severity_compiles_in_any_case(
    control: tuple[list[Any], list[Any]], marker: str
) -> None:
    """The control: each declaration is valid and keeps its severity."""
    rules, evidence = control
    compiled = [rule for rule in rules if rule.name == marker]

    assert compiled
    assert {rule.rule_type for rule in compiled} != {"compiler_invalid_param"}
    assert {rule.severity for rule in compiled} == {"warning"}
    assert _evidence_of(evidence, marker) == []


@pytest.mark.parametrize("marker", MARKERS)
def test_an_invalid_severity_drops_the_declaration(
    invalid: tuple[list[Any], list[Any]], marker: str
) -> None:
    """Each declaration gives one sentinel for ``severity`` and one evidence
    with the issue ``invalid_severity``, and no rule of its own."""
    rules, evidence = invalid
    declarations = _DECLARATIONS.get(marker, 1)
    compiled = [rule for rule in rules if rule.name == marker]

    assert [rule.rule_type for rule in compiled] == [
        "compiler_invalid_param"
    ] * declarations
    for sentinel in compiled:
        assert sentinel.rule_id.endswith("/invalid_declaration/severity") or (
            sentinel.rule_id.endswith("/invalid_param/severity")
        )
        assert sentinel.severity == "error"
        assert sentinel.params["param"] == "severity"
        assert sentinel.params["value"] == "fatal"
        assert sentinel.params["valid"] == _VALID
        assert sentinel.params["compiler_reason"] == _REASON
    reported = _evidence_of(evidence, marker)
    assert [item.payload["issue"] for item in reported] == [
        "invalid_severity"
    ] * declarations
    for item in reported:
        assert item.payload["param"] == "severity"
        assert item.payload["value"] == "fatal"
        assert sorted(item.payload["valid"]) == sorted(_VALID)
        assert item.payload["reason"] == _REASON
        assert "severity" not in item.payload


def test_no_sibling_rule_survives_an_invalid_severity(
    invalid: tuple[list[Any], list[Any]],
) -> None:
    rules, _ = invalid

    assert {rule.name for rule in rules} & _SIBLINGS == set()


def test_an_explicit_none_is_the_default_severity(tmp_path: Path) -> None:
    rules, evidence = compile_package(tmp_path, "None")

    assert {rule.name for rule in rules} - _SIBLINGS == set(MARKERS)
    assert {rule.severity for rule in rules if rule.name not in _SIBLINGS} == {"error"}
    assert [item for item in evidence if item.payload.get("issue")] == []
