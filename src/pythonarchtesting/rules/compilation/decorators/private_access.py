"""Compiler for ``forbid_private_access``.

Declared in a function or method body, it compiles to a static rule on that
entity (``ENC001``): the matched target may not read another object's
private attributes. The evaluator is ``execution.evaluators.private_access``.
"""

from __future__ import annotations

import ast
from typing import Any, List, Optional, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Rule, RuleSelector
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import with_rule_id_suffix
from .runtime_structure import invalid_param, invalid_target, marker_severity

MARKER = "forbid_private_access"
RULE_ID = "ENC001/forbid_private_access/v1"
_INVALID_PREFIX = f"ENC001/{MARKER}/invalid_declaration"
_SUPPORTED_KINDS = ("function", "method")
_PARAMS = ("allow", "severity", "message")


def _positional_count(raw: str) -> int:
    """How many positional arguments the marker's text passes."""
    try:
        node = ast.parse(raw, mode="eval").body
    except SyntaxError:
        return 0
    return len(node.args) if isinstance(node, ast.Call) else 0


def _problem(params: dict[str, Any], raw: str) -> Optional[tuple[str, str]]:
    """What is wrong with the marker's arguments, as ``(param, reason)``."""
    if _positional_count(raw):
        return ("args", f"{MARKER} takes no positional arguments; use allow=[...]")
    unknown = sorted(key for key in params if key not in _PARAMS)
    if unknown:
        return (
            unknown[0],
            f"unknown parameter {unknown[0]!r}; {MARKER} takes " + ", ".join(_PARAMS),
        )
    allow = params.get("allow", [])
    if not isinstance(allow, list) or not all(
        isinstance(name, str) and name.isidentifier() for name in allow
    ):
        return ("allow", "allow must be a list of attribute names")
    return None


def compile_forbid_private_access(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    params = dict(declaration.params)
    if source_entity.kind not in _SUPPORTED_KINDS:
        return invalid_target(
            source_entity, declaration, MARKER, list(_SUPPORTED_KINDS)
        )
    problem = _problem(params, declaration.raw)
    if problem is not None:
        return invalid_param(
            source_entity,
            declaration,
            marker=MARKER,
            rule_id_prefix=_INVALID_PREFIX,
            problem=problem,
            rule_id_suffix=rule_id_suffix,
        )
    allow = params.get("allow", [])
    rule = Rule(
        rule_id=with_rule_id_suffix(RULE_ID, rule_id_suffix),
        rule_type="private_access",
        name=MARKER,
        severity=marker_severity(params),
        scope=source_entity.kind,
        evidence_type="static",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id, explicit_target=None
        ),
        params={"allow": sorted(set(allow)), "fail_on_unmatched": True},
        message_template=(
            f"{MARKER} for " "{target.module_path}:{target.qualname}: {details.summary}"
        ),
        fix_hints=(
            "Read the object's state through its public methods or properties "
            "instead of its attributes starting with an underscore.",
        ),
        enabled=True,
    )
    return [rule], [], []


__all__ = ["RULE_ID", "compile_forbid_private_access"]
