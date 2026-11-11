"""Compiler for ``architecture_entry``.

Declared once, on the reference's root module (``__init__.py``), it compiles
to a static rule on that module, which compares the target's imports with the
reference's. Given ``entry`` and ``cases`` it also compiles to a runtime rule
on the entry function, which compares what the two do while the entry runs;
that one runs only with ``--dynamic``.
"""

from __future__ import annotations

from typing import Any, List, Tuple

from pythonarchtesting.architecture.compare import (
    DEFAULT_IGNORE_EXTERNAL,
    POLICIES,
    format_edge,
    parse_edge,
)
from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Rule, RuleSelector
from pythonarchtesting.entities import DeclarationEntry, Entity
from pythonarchtesting.execution.module_structure import in_module

from ..common import (
    InvalidParam,
    bool_param,
    options_problem,
    with_rule_id_suffix,
    without_none,
)
from .module_structure import entry_problem
from .runtime_structure import (
    case_params,
    invalid_target,
    marker_severity,
    rejected_declaration,
)

MARKER = "architecture_entry"
STATIC_RULE_ID = "DEP004/architecture_entry/v1"
RUNTIME_RULE_ID = "DYN011/architecture_entry/v1"
_INVALID_PREFIX = f"DEP004/{MARKER}/invalid_declaration"
_BOOLS = ("ignore_type_checking", "require_all")

_HINTS = (
    "Follow the module dependencies of the reference, or declare an "
    "exception with allow=[...] when the difference is intended.",
)


def _is_package_name(name: str) -> bool:
    return all(part.isidentifier() for part in name.split("."))


def _exceptions_problem(
    name: str, raw: Any, modules: set[str]
) -> tuple[str, str] | None:
    if raw is None:
        return None
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        return name, f"{name} must be a list of 'module -> module' strings"
    for item in raw:
        try:
            origin, end = parse_edge(item)
        except ValueError as error:
            return name, str(error)
        if not any(in_module(module, origin) for module in modules):
            return name, f"the reference has no module {origin!r}"
        known_end = any(in_module(module, end) for module in modules)
        if not known_end and not _is_package_name(end):
            return name, f"{end!r} is neither a module nor a package name"
    return None


def _problem(
    params: dict[str, Any], source_entities: List[Entity]
) -> tuple[str, str] | InvalidParam | None:
    policy = params.get("policy", "allow_new_modules")
    if policy not in POLICIES:
        return "policy", f"unknown policy {policy!r}; use one of {', '.join(POLICIES)}"
    bools = options_problem(params, bools=_BOOLS)
    if bools is not None:
        return bools
    if params.get("require_all") and not params.get("entry"):
        return "require_all", "require_all judges calls at run time: it needs an entry"
    ignore = params.get("ignore_external")
    if ignore is not None and (
        not isinstance(ignore, list) or not all(isinstance(i, str) for i in ignore)
    ):
        return "ignore_external", "ignore_external must be a list of package names"
    modules = {
        str(entity.module_path) for entity in source_entities if entity.module_path
    } | {"__init__"}
    for name in ("allow", "forbid"):
        problem = _exceptions_problem(name, params.get(name), modules)
        if problem is not None:
            return problem
    return None


def _model_params(params: dict[str, Any]) -> dict[str, Any]:
    ignore = params.get("ignore_external")
    return {
        "policy": params.get("policy", "allow_new_modules"),
        "allow": [format_edge(parse_edge(i)) for i in params.get("allow") or []],
        "forbid": [format_edge(parse_edge(i)) for i in params.get("forbid") or []],
        "ignore_external": list(DEFAULT_IGNORE_EXTERNAL if ignore is None else ignore),
        "ignore_type_checking": bool_param(
            params, "ignore_type_checking", default=True
        ),
    }


def compile_architecture_entry(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
    source_entities: List[Entity] | None = None,
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    entities = list(source_entities or [])
    params = without_none(declaration.params, ("policy", *_BOOLS))
    if source_entity.kind != "module" or source_entity.module_path:
        return invalid_target(source_entity, declaration, MARKER, ["root module"])

    problem: tuple[str, str] | InvalidParam | None = _problem(params, entities)
    entry_entity: Entity | None = None
    if problem is None:
        problem, entry_entity = entry_problem(params, entities, MARKER)
    rejected = rejected_declaration(
        source_entity,
        declaration,
        marker=MARKER,
        rule_id_prefix=_INVALID_PREFIX,
        problem=problem,
        rule_id_suffix=rule_id_suffix,
    )
    if rejected is not None:
        return rejected

    model = _model_params(params)
    rules = [
        Rule(
            rule_id=with_rule_id_suffix(STATIC_RULE_ID, rule_id_suffix),
            rule_type="architecture_static",
            name=MARKER,
            severity=marker_severity(params),
            scope=source_entity.kind,
            evidence_type="static",
            selector=RuleSelector(
                source_entity_id=source_entity.canonical_id, explicit_target=None
            ),
            params={**model, "fail_on_unmatched": True},
            message_template=f"{MARKER}: " "{details.summary}",
            fix_hints=_HINTS,
            enabled=True,
        )
    ]
    if entry_entity is not None:
        rules.append(
            Rule(
                rule_id=with_rule_id_suffix(RUNTIME_RULE_ID, rule_id_suffix),
                rule_type="architecture_runtime",
                name=MARKER,
                severity=marker_severity(params),
                scope=entry_entity.kind,
                evidence_type="runtime",
                selector=RuleSelector(
                    source_entity_id=entry_entity.canonical_id, explicit_target=None
                ),
                params={
                    **case_params(params),
                    **model,
                    "entry": params["entry"],
                    "require_all": bool_param(params, "require_all", default=False),
                },
                message_template=(
                    f"{MARKER} while "
                    "{target.module_path}:{target.qualname} "
                    "runs: {details.summary}"
                ),
                fix_hints=(
                    *_HINTS,
                    "Runs only with --dynamic; without it the rule is SKIPPED.",
                ),
                enabled=True,
            )
        )
    return rules, [], []


__all__ = ["RUNTIME_RULE_ID", "STATIC_RULE_ID", "compile_architecture_entry"]
