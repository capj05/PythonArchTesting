"""Compiler for ``module_interface``.

Declared on a module, it compiles to a static rule on that module, which
checks how the target's other modules import from it. Given ``entry`` and
``cases`` it also compiles to a runtime rule on the entry function, which
checks the calls other modules make into it while the entry runs; that one
runs only with ``--dynamic``.
"""

from __future__ import annotations

import ast
from typing import Any, List, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Rule, RuleSelector
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    InvalidParam,
    bool_param,
    bool_problem,
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

MARKER = "module_interface"
STATIC_RULE_ID = "DEP005/module_interface/v1"
RUNTIME_RULE_ID = "DYN012/module_interface/v1"
_INVALID_PREFIX = f"DEP005/{MARKER}/invalid_declaration"
_HINTS = (
    "Use the module through its public names only; if another name is meant "
    "to be used from outside, add it to the module's interface.",
)


def _defined_names(module: Entity, entities: List[Entity]) -> set[str]:
    """Every top-level name of ``module``: entities, assignments, imports, submodules."""
    names = {
        str(entity.qualname).split(".")[0]
        for entity in entities
        if entity.module_path == module.module_path and entity.kind != "module"
    }
    prefix = f"{module.module_path}." if module.module_path else ""
    for entity in entities:
        path = str(entity.module_path)
        if (
            entity.kind == "module"
            and path
            and path.startswith(prefix)
            and path != module.module_path
        ):
            names.add(path[len(prefix) :].split(".")[0])
    tree = module.extras.get("ast_node")
    for node in getattr(tree, "body", []) or []:
        if isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(
                alias.asname or alias.name.split(".")[0] for alias in node.names
            )
    return names


def _problem(
    module: Entity, params: dict[str, Any], entities: List[Entity]
) -> tuple[str, str] | InvalidParam | None:
    names = params.get("names") or []
    if not isinstance(names, list) or not all(isinstance(n, str) and n for n in names):
        return "names", "names must be the module's top-level names"
    defined = _defined_names(module, entities)
    missing = [name for name in names if name not in defined]
    if missing:
        return "names", f"the module defines no {', '.join(repr(n) for n in missing)}"
    return bool_problem(params, "ignore_type_checking")


def compile_module_interface(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
    source_entities: List[Entity] | None = None,
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    entities = list(source_entities or [])
    params = without_none(declaration.params, ("ignore_type_checking",))
    if source_entity.kind != "module":
        return invalid_target(
            source_entity,
            declaration,
            MARKER,
            ["module"],
            rule_id_prefix=_INVALID_PREFIX,
            rule_id_suffix=rule_id_suffix,
        )
    problem: tuple[str, str] | InvalidParam | None = _problem(
        source_entity, params, entities
    )
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
    interface = {
        "names": list(params.get("names") or []),
        "module": str(source_entity.module_path),
        "ignore_type_checking": bool_param(
            params, "ignore_type_checking", default=True
        ),
    }
    rules = [
        Rule(
            rule_id=with_rule_id_suffix(STATIC_RULE_ID, rule_id_suffix),
            rule_type="module_interface",
            name=MARKER,
            severity=marker_severity(params),
            scope=source_entity.kind,
            evidence_type="static",
            selector=RuleSelector(
                source_entity_id=source_entity.canonical_id, explicit_target=None
            ),
            params={**interface, "fail_on_unmatched": True},
            message_template=f"{MARKER}: " "{details.summary}",
            fix_hints=_HINTS,
            enabled=True,
        )
    ]
    if entry_entity is not None:
        rules.append(
            Rule(
                rule_id=with_rule_id_suffix(RUNTIME_RULE_ID, rule_id_suffix),
                rule_type="runtime_module_interface",
                name=MARKER,
                severity=marker_severity(params),
                scope=entry_entity.kind,
                evidence_type="runtime",
                selector=RuleSelector(
                    source_entity_id=entry_entity.canonical_id, explicit_target=None
                ),
                params={**case_params(params), **interface, "entry": params["entry"]},
                message_template=(
                    f"{MARKER} while "
                    "{target.module_path}:{target.qualname} runs: {details.summary}"
                ),
                fix_hints=(
                    *_HINTS,
                    "Runs only with --dynamic; without it the rule is SKIPPED.",
                ),
                enabled=True,
            )
        )
    return rules, [], []


__all__ = ["RUNTIME_RULE_ID", "STATIC_RULE_ID", "compile_module_interface"]
