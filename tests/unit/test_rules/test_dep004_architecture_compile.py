"""Compiling ``architecture_entry`` (DEP004, DYN011)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pythonarchtesting.config.loader import load_config
from pythonarchtesting.rules.compilation import compile_rules
from pythonarchtesting.runner.source_prep import prepare_source

_MODULES = {
    "controller.py": "def handle(request, service):\n    return service\n",
    "service.py": "class Service:\n    def run(self):\n        return 1\n",
    "models.py": "class Order:\n    pass\n",
}
_HEADER = (
    "from typing import Annotated\n"
    "from pythonarchtesting.rules import architecture_entry\n\n"
)


def _reference(tmp_path: Path, markers: str | None, where: str = "__init__.py") -> Path:
    root = tmp_path / "reference"
    root.mkdir()
    for name, text in _MODULES.items():
        (root / name).write_text(text, encoding="utf-8")
    if markers is not None:
        target = root / where
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        target.write_text(
            _HEADER + existing + f"\n__archtest__: Annotated[None, {markers}]\n",
            encoding="utf-8",
        )
    return root


def _rules(tmp_path: Path, markers: str | None, **kwargs) -> list:
    root = _reference(tmp_path, markers)
    state = prepare_source(config=load_config(), source_path=root, **kwargs)
    return [rule for rule in state.rules if "architecture" in rule.rule_id]


def test_declaration_compiles_to_a_static_rule_on_the_root_module(tmp_path: Path):
    (rule,) = _rules(tmp_path, "architecture_entry()")

    assert rule.rule_id == "DEP004/architecture_entry/v1"
    assert rule.rule_type == "architecture_static"
    assert rule.evidence_type == "static"
    assert rule.selector.source_entity_id == "source:source:::module:-"
    assert rule.params["policy"] == "allow_new_modules"
    assert rule.params["allow"] == []
    assert rule.params["forbid"] == []
    assert "pickle" not in rule.params["ignore_external"]
    assert "__future__" in rule.params["ignore_external"]
    assert rule.params["fail_on_unmatched"] is True


def test_exceptions_are_stored_normalised(tmp_path: Path):
    (rule,) = _rules(
        tmp_path,
        'architecture_entry(policy="layered", allow=["controller->models"], '
        'forbid=[" service  ->  pickle "], ignore_external=["json"])',
    )

    assert rule.params["policy"] == "layered"
    assert rule.params["allow"] == ["controller -> models"]
    assert rule.params["forbid"] == ["service -> pickle"]
    assert rule.params["ignore_external"] == ["json"]


def test_entry_with_cases_adds_dyn011_on_the_entry(tmp_path: Path):
    rules = _rules(
        tmp_path,
        'architecture_entry(entry="controller.handle", '
        'cases=[{"args": [{}, {"$new": "service.Service"}]}])',
    )

    static, runtime = sorted(rules, key=lambda rule: rule.rule_id)
    assert static.rule_id == "DEP004/architecture_entry/v1"
    assert runtime.rule_id == "DYN011/architecture_entry/v1"
    assert runtime.rule_type == "architecture_runtime"
    assert runtime.evidence_type == "runtime"
    assert ":controller:handle:function:" in runtime.selector.source_entity_id
    assert runtime.params["entry"] == "controller.handle"
    assert runtime.params["policy"] == "allow_new_modules"
    assert runtime.params["cases"] == [{"args": [{}, {"$new": "service.Service"}]}]


@pytest.mark.parametrize(
    ("markers", "param", "reason"),
    [
        ('architecture_entry(policy="loose")', "policy", "loose"),
        ('architecture_entry(allow=["service->"])', "allow", "module -> module"),
        ('architecture_entry(allow="service -> models")', "allow", "list"),
        ('architecture_entry(forbid=["nowhere -> service"])', "forbid", "nowhere"),
        ('architecture_entry(allow=["service -> pick le"])', "allow", "pick le"),
        ("architecture_entry(ignore_external=[1])", "ignore_external", "names"),
        (
            'architecture_entry(entry="controller.missing", cases=[{"args": []}])',
            "entry",
            "no function",
        ),
        ('architecture_entry(cases=[{"args": []}])', "entry", "need an entry"),
        ('architecture_entry(entry="controller.handle")', "cases", "non-empty"),
    ],
)
def test_invalid_declarations_become_invalid_param_rules(
    tmp_path: Path, markers: str, param: str, reason: str
):
    root = _reference(tmp_path, markers)
    state = prepare_source(config=load_config(), source_path=root)
    (rule,) = [rule for rule in state.rules if "architecture_entry" in rule.rule_id]

    assert rule.rule_id.startswith("DEP004/architecture_entry/invalid_declaration")
    assert rule.rule_type == "compiler_invalid_param"
    assert rule.params["param"] == param
    assert reason in rule.params["compiler_reason"]


def test_an_external_package_may_stand_on_the_right_of_an_exception(tmp_path: Path):
    (rule,) = _rules(tmp_path, 'architecture_entry(allow=["service -> pickle"])')

    assert rule.rule_id == "DEP004/architecture_entry/v1"


def test_declaration_outside_the_root_module_is_an_invalid_target(tmp_path: Path):
    root = _reference(tmp_path, "architecture_entry()", where="service.py")

    state = prepare_source(config=load_config(), source_path=root)
    rules, evidence, _ = compile_rules(list(state.source_by_id.values()), load_config())

    # The misplaced marker is a FAILED sentinel, not missing from the report.
    assert [
        (rule.rule_type, rule.params["param"], rule.params["valid"])
        for rule in rules
        if rule.name == "architecture_entry"
    ] == [("compiler_invalid_param", "target_kind", ["root module"])]
    assert [item.type for item in evidence] == ["compiler_invalid_target"]


def _compiled(tmp_path: Path, markers: str | None, architecture: bool) -> list:
    root = _reference(tmp_path, markers)
    (root / "__init__.py").touch()
    state = prepare_source(config=load_config(), source_path=root)
    rules, _, _ = compile_rules(
        list(state.source_by_id.values()), load_config(), architecture=architecture
    )
    return [rule for rule in rules if "architecture" in rule.rule_id]


def test_flag_without_declaration_adds_only_the_static_rule(tmp_path: Path):
    (rule,) = _compiled(tmp_path, None, architecture=True)

    assert rule.rule_id == "DEP004/architecture_entry/v1"
    assert rule.selector.source_entity_id == "source:source:::module:-"
    assert rule.params["policy"] == "allow_new_modules"


def test_flag_with_declaration_adds_no_duplicate(tmp_path: Path):
    rules = _compiled(
        tmp_path, 'architecture_entry(policy="strict")', architecture=True
    )

    assert [rule.rule_id for rule in rules] == ["DEP004/architecture_entry/v1"]
    assert rules[0].params["policy"] == "strict"


def test_without_flag_and_declaration_nothing_is_added(tmp_path: Path):
    assert _compiled(tmp_path, None, architecture=False) == []


def test_flag_reaches_compilation_through_prepare_source(tmp_path: Path):
    root = _reference(tmp_path, None)
    (root / "__init__.py").touch()

    state = prepare_source(config=load_config(), source_path=root, architecture=True)

    assert [rule.rule_id for rule in state.rules if "architecture" in rule.rule_id] == [
        "DEP004/architecture_entry/v1"
    ]


def test_require_all_reaches_the_runtime_rule_only(tmp_path: Path):
    rules = _rules(
        tmp_path,
        'architecture_entry(require_all=True, entry="controller.handle", '
        'cases=[{"args": [{}, {"$new": "service.Service"}]}])',
    )

    static, runtime = sorted(rules, key=lambda rule: rule.rule_id)
    assert runtime.params["require_all"] is True
    assert "require_all" not in static.params


def test_require_all_defaults_to_false(tmp_path: Path):
    rules = _rules(
        tmp_path,
        'architecture_entry(entry="controller.handle", '
        'cases=[{"args": [{}, {"$new": "service.Service"}]}])',
    )

    assert max(rules, key=lambda rule: rule.rule_id).params["require_all"] is False


def test_require_all_must_be_a_bool(tmp_path: Path):
    root = _reference(tmp_path, 'architecture_entry(require_all="yes")')
    state = prepare_source(config=load_config(), source_path=root)
    (rule,) = [rule for rule in state.rules if "architecture_entry" in rule.rule_id]

    assert rule.params["param"] == "require_all"


@pytest.mark.parametrize(
    ("markers", "param", "reason"),
    [
        ('architecture_entry(allow=["services -> models"])', "allow", "services"),
        ("architecture_entry(require_all=True)", "require_all", "entry"),
    ],
)
def test_more_invalid_declarations(
    tmp_path: Path, markers: str, param: str, reason: str
):
    root = _reference(tmp_path, markers)
    state = prepare_source(config=load_config(), source_path=root)
    (rule,) = [rule for rule in state.rules if "architecture_entry" in rule.rule_id]

    assert rule.params["param"] == param
    assert reason in rule.params["compiler_reason"]
