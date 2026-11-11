from __future__ import annotations

from typing import Any, List, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Rule, RuleSelector
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    invalid_target_evidence,
    marker_severity,
    reject_invalid_severity,
    with_rule_id_suffix,
)


def compile_is_enum(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    params_kwargs = dict(declaration.params)
    if source_entity.kind != "class":
        return (
            [],
            [
                invalid_target_evidence(
                    source_entity, declaration, decorator="is_enum", key="declaration"
                )
            ],
            [],
        )

    rejected = reject_invalid_severity(
        source_entity,
        declaration,
        marker="is_enum",
        rule_id_prefix="ENUM001/is_enum/invalid_declaration",
        rule_id_suffix=rule_id_suffix,
        key="declaration",
    )
    if rejected is not None:
        return rejected

    base_severity = marker_severity(params_kwargs)

    rule = Rule(
        rule_id=with_rule_id_suffix("ENUM001/is_enum/v1", rule_id_suffix),
        rule_type="enum_type",
        name="is_enum",
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params={
            "fail_on_unmatched": True,
        },
        message_template=(
            "Enum classification mismatch for "
            "{target.module_path}:{target.qualname}: {details.reason}"
        ),
        fix_hints=(
            (
                "Inherit from enum.Enum, enum.IntEnum, enum.StrEnum, "
                "enum.Flag, or enum.IntFlag."
            ),
            "Local subclasses of enum-like classes also satisfy the rule.",
        ),
        enabled=True,
    )
    return [rule], [], []


__all__ = ["compile_is_enum"]
