"""Compilers for ``enforce_layers`` and ``forbid_cycles``.

Both are declared once, on the project's root module (``__init__.py``), and
compile to a static rule on that module. Given ``entry`` and ``cases``, each
also compiles to a runtime rule on the entry function, which runs only with
``--dynamic``: the runtime machinery calls a function, so the rule is
attached to the function whose call tree it observes.
"""

from __future__ import annotations

from typing import Any, List, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Rule, RuleSelector
from pythonarchtesting.entities import DeclarationEntry, Entity
from pythonarchtesting.execution.module_structure import in_module, parse_layers

from ..common import (
    InvalidParam,
    bool_param,
    bool_problem,
    with_rule_id_suffix,
    without_none,
)
from .runtime_structure import (
    case_params,
    invalid_target,
    marker_severity,
    rejected_declaration,
    runtime_cases_problem,
)

_ENTRY_KINDS = frozenset({"function", "method"})

# marker -> (static rule id, static rule type, runtime rule id, runtime type)
_RULES = {
    "enforce_layers": (
        "DEP002/enforce_layers/v1",
        "module_layers",
        "DYN009/enforce_layers/v1",
        "runtime_layers",
    ),
    "forbid_cycles": (
        "DEP003/forbid_cycles/v1",
        "module_cycles",
        "DYN010/forbid_cycles/v1",
        "runtime_cycles",
    ),
}

_HINTS = {
    "enforce_layers": (
        "Move the code that uses a higher layer up into that layer, or pass "
        "what it needs down as an argument.",
    ),
    "forbid_cycles": (
        "Break the cycle: move what both modules need into a module of its "
        "own, or pass it in as an argument.",
    ),
}


def _entry_entity(entry: str, source_entities: List[Entity]) -> Entity | None:
    for entity in source_entities:
        if entity.kind not in _ENTRY_KINDS:
            continue
        name = (
            f"{entity.module_path}.{entity.qualname}"
            if entity.module_path
            else str(entity.qualname)
        )
        if name == entry:
            return entity
    return None


def entry_problem(
    params: dict[str, Any], source_entities: List[Entity], marker: str
) -> tuple[tuple[str, str] | None, Entity | None]:
    """Check a project-wide marker's ``entry`` and ``cases``.

    Returns the problem, if any, and the reference function ``entry`` names
    (``None`` when the marker declares no runtime part).
    """
    entry = params.get("entry")
    if entry is None and params.get("cases") is None:
        return None, None
    if not isinstance(entry, str) or not entry:
        return ("entry", "runtime cases need an entry: 'module.function'"), None
    entry_entity = _entry_entity(entry, source_entities)
    if entry_entity is None:
        return ("entry", f"the reference has no function {entry!r}"), None
    return runtime_cases_problem(params, entry_entity.kind, marker), entry_entity


def _structure_problem(
    marker: str, params: dict[str, Any], source_entities: List[Entity]
) -> tuple[str, str] | InvalidParam | None:
    problem = bool_problem(params, "ignore_type_checking")
    if problem is not None or marker != "enforce_layers":
        return problem
    raw = params.get("layers")
    if (
        not isinstance(raw, list)
        or not raw
        or not all(isinstance(item, str) for item in raw)
    ):
        return "layers", "give the layers as module names, highest first"
    closed = [] if params.get("closed") is None else params["closed"]
    if not isinstance(closed, list) or not all(isinstance(i, str) for i in closed):
        return "closed", "closed must be a list of module names"
    try:
        layers = parse_layers(raw, closed)
    except ValueError as error:
        return ("closed" if "closed" in str(error) else "layers"), str(error)
    modules = {entity.module_path for entity in source_entities if entity.module_path}
    for layer in layers:
        for member in layer.modules:
            if not any(in_module(module, member) for module in modules):
                return "layers", f"the reference has no module {member!r}"
    return None


def _structure_params(marker: str, params: dict[str, Any]) -> dict[str, Any]:
    compiled: dict[str, Any] = {
        "ignore_type_checking": bool_param(params, "ignore_type_checking", default=True)
    }
    if marker == "enforce_layers":
        compiled["layers"] = list(params["layers"])
        compiled["closed"] = list(params.get("closed") or [])
    return compiled


def _compile_module_structure(
    marker: str,
    source_entity: Entity,
    declaration: DeclarationEntry,
    rule_id_suffix: str,
    source_entities: List[Entity],
) -> Tuple[List[Any], List[Any], List[Any]]:
    static_id, static_type, runtime_id, runtime_type = _RULES[marker]
    params = without_none(declaration.params, ("ignore_type_checking",))
    if source_entity.kind != "module":
        return invalid_target(source_entity, declaration, marker, ["module"])

    problem: tuple[str, str] | InvalidParam | None = _structure_problem(
        marker, params, source_entities
    )
    entry_entity: Entity | None = None
    entry = params.get("entry")
    if problem is None:
        problem, entry_entity = entry_problem(params, source_entities, marker)
    rejected = rejected_declaration(
        source_entity,
        declaration,
        marker=marker,
        rule_id_prefix=f"{static_id.split('/')[0]}/{marker}/invalid_declaration",
        problem=problem,
        rule_id_suffix=rule_id_suffix,
    )
    if rejected is not None:
        return rejected

    structure = _structure_params(marker, params)
    rules = [
        Rule(
            rule_id=with_rule_id_suffix(static_id, rule_id_suffix),
            rule_type=static_type,
            name=marker,
            severity=marker_severity(params),
            scope=source_entity.kind,
            evidence_type="static",
            selector=RuleSelector(
                source_entity_id=source_entity.canonical_id,
                explicit_target=None,
            ),
            params={**structure, "fail_on_unmatched": True},
            message_template=f"{marker}: " "{details.summary}",
            fix_hints=_HINTS[marker],
            enabled=True,
        )
    ]
    if entry_entity is not None:
        rules.append(
            Rule(
                rule_id=with_rule_id_suffix(runtime_id, rule_id_suffix),
                rule_type=runtime_type,
                name=marker,
                severity=marker_severity(params),
                scope=entry_entity.kind,
                evidence_type="runtime",
                selector=RuleSelector(
                    source_entity_id=entry_entity.canonical_id,
                    explicit_target=None,
                ),
                params={**case_params(params), **structure, "entry": entry},
                message_template=(
                    f"{marker} while "
                    "{target.module_path}:{target.qualname} "
                    "runs: {details.summary}"
                ),
                fix_hints=(
                    *_HINTS[marker],
                    "Runs only with --dynamic; without it the rule is SKIPPED.",
                ),
                enabled=True,
            )
        )
    return rules, [], []


def compile_enforce_layers(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
    source_entities: List[Entity] | None = None,
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    return _compile_module_structure(
        "enforce_layers",
        source_entity,
        declaration,
        rule_id_suffix,
        list(source_entities or []),
    )


def compile_forbid_cycles(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
    source_entities: List[Entity] | None = None,
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    return _compile_module_structure(
        "forbid_cycles",
        source_entity,
        declaration,
        rule_id_suffix,
        list(source_entities or []),
    )


__all__ = ["compile_enforce_layers", "compile_forbid_cycles", "entry_problem"]
