from __future__ import annotations

from typing import Any, List, Literal, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence, Rule, RuleSelector
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import canonicalize_payload, evidence_id, with_rule_id_suffix


def _evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    evidence_type: str,
    payload: dict[str, Any],
) -> Evidence:
    location = {
        "filepath": source_entity.filepath_rel,
        "lineno": declaration.lineno or source_entity.lineno,
        "col": declaration.col,
    }
    return Evidence(
        evidence_id=evidence_id(evidence_type, payload),
        type=evidence_type,
        source="compiler",
        role="source",
        entity_id=source_entity.canonical_id,
        payload=canonicalize_payload(payload),
        location=location,
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
    base_severity_raw = str(params_kwargs.get("severity", "error")).lower()
    if base_severity_raw in {"error", "warning", "info"}:
        base_severity = cast(Literal["error", "warning", "info"], base_severity_raw)
    else:
        base_severity = "error"

    if source_entity.kind != "class":
        payload = {
            "declaration": "is_enum",
            "issue": "compiler_invalid_target",
            "expected_kind": "class",
            "found_kind": source_entity.kind,
        }
        return (
            [],
            [
                _evidence(
                    source_entity,
                    declaration,
                    evidence_type="compiler_invalid_target",
                    payload=payload,
                )
            ],
            [],
        )

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
