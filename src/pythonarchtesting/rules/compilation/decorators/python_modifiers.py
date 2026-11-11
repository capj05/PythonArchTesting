from __future__ import annotations

from typing import Any, List, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Rule, RuleSelector
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import (
    invalid_target_evidence,
    marker_severity,
    with_rule_id_suffix,
)


def _compile_python_modifier_rule(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    declaration_name: str,
    modifier_kind: str,
    rule_id: str,
    expected_kind: str,
    fix_hint_subject: str,
    positive: bool,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    _ = cfg
    params_kwargs = dict(declaration.params)
    base_severity = marker_severity(params_kwargs)

    if source_entity.kind != expected_kind:
        return (
            [],
            [
                invalid_target_evidence(
                    source_entity,
                    declaration,
                    decorator=declaration_name,
                    expected_kind=expected_kind,
                )
            ],
            [],
        )

    rule = Rule(
        rule_id=with_rule_id_suffix(rule_id, rule_id_suffix),
        rule_type="python_modifier",
        name=declaration_name,
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=RuleSelector(
            source_entity_id=source_entity.canonical_id,
            explicit_target=None,
        ),
        params={
            "modifier_kind": modifier_kind,
            "modifier_polarity": "positive" if positive else "negative",
            "fail_on_unmatched": True,
        },
        message_template=(
            "Python modifier mismatch for "
            "{target.module_path}:{target.qualname}: {details.reason}"
        ),
        fix_hints=(
            (
                f"Align the target {fix_hint_subject} with the required "
                "Python modifier classification."
            ),
            "Use recognized Python decorators for abstract/final contracts.",
        ),
        enabled=True,
    )
    return [rule], [], []


def compile_is_abstract_class(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    return _compile_python_modifier_rule(
        source_entity,
        declaration,
        cfg,
        declaration_name="is_abstract_class",
        modifier_kind="abstract_class",
        rule_id="MOD001/is_abstract_class/v1",
        expected_kind="class",
        fix_hint_subject="class",
        positive=True,
        rule_id_suffix=rule_id_suffix,
    )


def compile_is_concrete_class(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    return _compile_python_modifier_rule(
        source_entity,
        declaration,
        cfg,
        declaration_name="is_concrete_class",
        modifier_kind="concrete_class",
        rule_id="MOD001/is_concrete_class/v1",
        expected_kind="class",
        fix_hint_subject="class",
        positive=True,
        rule_id_suffix=rule_id_suffix,
    )


def compile_is_final_class(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    return _compile_python_modifier_rule(
        source_entity,
        declaration,
        cfg,
        declaration_name="is_final_class",
        modifier_kind="final_class",
        rule_id="MOD001/is_final_class/v1",
        expected_kind="class",
        fix_hint_subject="class",
        positive=True,
        rule_id_suffix=rule_id_suffix,
    )


def compile_is_abstract_method(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    return _compile_python_modifier_rule(
        source_entity,
        declaration,
        cfg,
        declaration_name="is_abstract_method",
        modifier_kind="abstract_method",
        rule_id="MOD002/is_abstract_method/v1",
        expected_kind="method",
        fix_hint_subject="method",
        positive=True,
        rule_id_suffix=rule_id_suffix,
    )


def compile_is_final_method(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    return _compile_python_modifier_rule(
        source_entity,
        declaration,
        cfg,
        declaration_name="is_final_method",
        modifier_kind="final_method",
        rule_id="MOD002/is_final_method/v1",
        expected_kind="method",
        fix_hint_subject="method",
        positive=True,
        rule_id_suffix=rule_id_suffix,
    )


def compile_is_non_final_class(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    return _compile_python_modifier_rule(
        source_entity,
        declaration,
        cfg,
        declaration_name="is_non_final_class",
        modifier_kind="non_final_class",
        rule_id="MOD003/is_non_final_class/v1",
        expected_kind="class",
        fix_hint_subject="class",
        positive=False,
        rule_id_suffix=rule_id_suffix,
    )


def compile_is_non_abstract_method(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    return _compile_python_modifier_rule(
        source_entity,
        declaration,
        cfg,
        declaration_name="is_non_abstract_method",
        modifier_kind="non_abstract_method",
        rule_id="MOD003/is_non_abstract_method/v1",
        expected_kind="method",
        fix_hint_subject="method",
        positive=False,
        rule_id_suffix=rule_id_suffix,
    )


def compile_is_non_final_method(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    return _compile_python_modifier_rule(
        source_entity,
        declaration,
        cfg,
        declaration_name="is_non_final_method",
        modifier_kind="non_final_method",
        rule_id="MOD003/is_non_final_method/v1",
        expected_kind="method",
        fix_hint_subject="method",
        positive=False,
        rule_id_suffix=rule_id_suffix,
    )


__all__ = [
    "compile_is_abstract_class",
    "compile_is_abstract_method",
    "compile_is_concrete_class",
    "compile_is_final_class",
    "compile_is_final_method",
    "compile_is_non_abstract_method",
    "compile_is_non_final_class",
    "compile_is_non_final_method",
]
