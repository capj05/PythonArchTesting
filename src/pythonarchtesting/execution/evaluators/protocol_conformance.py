from __future__ import annotations

from typing import Any, Dict, List, Literal, Tuple

from pythonarchtesting.core.evidence import get_ast_annotations, get_ast_signature
from pythonarchtesting.core.models import (
    EvalContext,
    Evidence,
    Rule,
    RuleResult,
    RuleStatus,
)
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult
from pythonarchtesting.protocols.introspection import (
    ProtocolAttribute,
    class_attributes,
    class_methods,
    protocol_attributes,
    protocol_methods,
)
from pythonarchtesting.protocols.reference_resolution import resolve_reference
from pythonarchtesting.protocols.signature_inference import (
    infer_signature_target_reference,
)
from pythonarchtesting.protocols.signature_slots import signature_subject_annotation

from .annotation_compatibility import compare_annotation_text
from .api_signature import evaluate_method_compatibility
from .messages import _build_rule_result


def _class_methods(entity: Entity, ctx: EvalContext, role: str) -> dict[str, Entity]:
    entities = (
        ctx.source_index.all_sorted if role == "source" else ctx.target_index.all_sorted
    )
    collector = protocol_methods if role == "source" else class_methods
    return {method.name: method for method in collector(entity, entities)}


def _class_attributes(
    entity: Entity, ctx: EvalContext, role: str
) -> dict[str, ProtocolAttribute]:
    entities = (
        ctx.source_index.all_sorted if role == "source" else ctx.target_index.all_sorted
    )
    collector = protocol_attributes if role == "source" else class_attributes
    return {attribute.name: attribute for attribute in collector(entity, entities)}


def _method_evidence(
    ctx: EvalContext,
    source_method: Entity,
    target_method: Entity,
) -> Tuple[Evidence, ...]:
    return (
        get_ast_signature(ctx, source_method.canonical_id, "source"),
        get_ast_signature(ctx, target_method.canonical_id, "target"),
        get_ast_annotations(ctx, source_method.canonical_id, "source"),
        get_ast_annotations(ctx, target_method.canonical_id, "target"),
    )


def _protocol_details(
    protocol_entity: Entity,
) -> dict[str, Any]:
    return {
        "entity_id": protocol_entity.canonical_id,
        "module_path": protocol_entity.module_path,
        "qualname": protocol_entity.qualname,
        "name": protocol_entity.name,
    }


def _attribute_variance(
    required_attribute: ProtocolAttribute,
) -> Literal["invariant", "covariant", "contravariant"]:
    if required_attribute.kind == "property" and not required_attribute.is_writable:
        return "covariant"
    return "invariant"


def _attribute_requirement_errors(
    *,
    required_attribute: ProtocolAttribute,
    target_attribute: ProtocolAttribute,
    protocol_entity: Entity,
    target_class: Entity,
    ctx: EvalContext,
) -> list[str]:
    errors: list[str] = []

    if required_attribute.is_writable and not target_attribute.is_writable:
        errors.append(
            "attribute mutability mismatch: protocol requires writable member"
        )

    if required_attribute.annotation is None:
        return errors

    # `ClassVar[...]` protocol annotations are intentionally deferred: we compare
    # their normalized inner annotation and do not enforce class-vs-instance
    # semantics as a distinct protocol rule.
    comparison = compare_annotation_text(
        expected=required_attribute.annotation,
        found=target_attribute.annotation,
        expected_entity=protocol_entity,
        found_entity=target_class,
        ctx=ctx,
        variance=_attribute_variance(required_attribute),
    )
    if not comparison.compatible:
        errors.append(
            "attribute annotation mismatch: "
            f"expected {comparison.expected}, found {comparison.found}"
        )
    return errors


def _evaluate_protocol_against_class(
    *,
    protocol_entity: Entity,
    target_class: Entity,
    ctx: EvalContext,
    mode: str,
    enforce_method_kind: bool,
    return_annotation: str,
) -> tuple[
    list[str],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[Evidence],
    list[str],
    list[str],
    list[str],
    list[str],
    list[str],
    list[str],
]:
    required_methods = _class_methods(protocol_entity, ctx, "source")
    required_attributes = _class_attributes(protocol_entity, ctx, "source")
    target_methods = _class_methods(target_class, ctx, "target")
    target_attributes = _class_attributes(target_class, ctx, "target")

    missing_methods: List[str] = []
    missing_attributes: List[str] = []
    signature_errors: List[dict[str, Any]] = []
    attribute_errors: List[dict[str, Any]] = []
    return_warnings: List[dict[str, Any]] = []
    evidence: List[Evidence] = []

    for method_name, source_method in required_methods.items():
        target_method = target_methods.get(method_name)
        if target_method is None:
            missing_methods.append(method_name)
            continue

        result = evaluate_method_compatibility(
            source_method,
            target_method,
            ctx=ctx,
            mode=mode,
            enforce_method_kind=enforce_method_kind,
            check_return=return_annotation != "off",
        )
        evidence.extend(_method_evidence(ctx, source_method, target_method))
        if result["errors"]:
            signature_errors.append({"method": method_name, "errors": result["errors"]})
        if result["return_errors"]:
            record = {"method": method_name, "errors": result["return_errors"]}
            if return_annotation == "error":
                signature_errors.append(record)
            else:
                return_warnings.append(record)

    for attribute_name, required_attribute in required_attributes.items():
        target_attribute = target_attributes.get(attribute_name)
        if target_attribute is None:
            missing_attributes.append(attribute_name)
            continue
        errors = _attribute_requirement_errors(
            required_attribute=required_attribute,
            target_attribute=target_attribute,
            protocol_entity=protocol_entity,
            target_class=target_class,
            ctx=ctx,
        )
        if errors:
            attribute_errors.append(
                {
                    "attribute": attribute_name,
                    "errors": errors,
                }
            )

    hard_errors: List[str] = []
    if missing_methods:
        hard_errors.append(
            f"missing protocol methods: {', '.join(sorted(missing_methods))}"
        )
    if missing_attributes:
        hard_errors.append(
            f"missing protocol attributes: {', '.join(sorted(missing_attributes))}"
        )
    for record in signature_errors:
        hard_errors.append(
            f"{record['method']}: {'; '.join(str(item) for item in record['errors'])}"
        )
    for record in attribute_errors:
        hard_errors.append(
            f"{record['attribute']}: {'; '.join(str(item) for item in record['errors'])}"
        )

    return (
        hard_errors,
        signature_errors,
        attribute_errors,
        return_warnings,
        evidence,
        sorted(missing_methods),
        sorted(required_methods.keys()),
        sorted(target_methods.keys()),
        sorted(missing_attributes),
        sorted(required_attributes.keys()),
        sorted(target_attributes.keys()),
    )


class ProtocolConformanceEvaluator:
    """Evaluator for class-level and signature-level protocol rules."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        protocol_entity_id = str(rule.params.get("protocol_entity_id", ""))
        protocol_entity = ctx.source_by_id.get(protocol_entity_id)
        if protocol_entity is None:
            raise ValueError(
                f"Protocol source entity not found for rule {rule.rule_id}: {protocol_entity_id}"
            )

        if rule.name == "implements_protocol_signature":
            return self._evaluate_signature_rule(
                rule, source, target, match, ctx, protocol_entity
            )
        return self._evaluate_class_rule(
            rule, source, target, match, ctx, protocol_entity
        )

    def _evaluate_class_rule(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
        protocol_entity: Entity,
    ) -> RuleResult:
        mode = str(rule.params.get("signature_mode", "compatible")).lower()
        enforce_method_kind = bool(rule.params.get("enforce_method_kind", True))
        return_annotation = str(rule.params.get("return_annotation", "warning")).lower()

        (
            hard_errors,
            signature_errors,
            attribute_errors,
            return_warnings,
            evidence,
            missing_methods,
            required_methods,
            target_methods,
            missing_attributes,
            required_attributes,
            target_attributes,
        ) = _evaluate_protocol_against_class(
            protocol_entity=protocol_entity,
            target_class=target,
            ctx=ctx,
            mode=mode,
            enforce_method_kind=enforce_method_kind,
            return_annotation=return_annotation,
        )

        status: RuleStatus = "FAILED" if hard_errors else "OK"
        details: Dict[str, Any] = {
            "reason": (
                "Protocol requirement satisfied."
                if not hard_errors
                else "; ".join(hard_errors)
            ),
            "protocol": _protocol_details(protocol_entity),
            "missing_methods": missing_methods,
            "missing_attributes": missing_attributes,
            "signature_errors": signature_errors,
            "attribute_errors": attribute_errors,
            "return_warnings": return_warnings,
            "required_methods": required_methods,
            "required_attributes": required_attributes,
            "target_methods": target_methods,
            "target_attributes": target_attributes,
            "signature_mode": mode,
            "enforce_method_kind": enforce_method_kind,
            "return_annotation": return_annotation,
        }
        return _build_rule_result(
            rule,
            source,
            target,
            match,
            status,
            details,
            tuple(evidence),
        )

    def _evaluate_signature_rule(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
        protocol_entity: Entity,
    ) -> RuleResult:
        subject_kind = str(rule.params.get("subject_kind", ""))
        subject_index = int(rule.params.get("subject_index", -1))
        subject_name = str(rule.params.get("subject_name", ""))
        target_annotation = signature_subject_annotation(
            target,
            subject_kind=subject_kind,
            subject_index=subject_index,
        )
        source_annotation = signature_subject_annotation(
            source,
            subject_kind=subject_kind,
            subject_index=subject_index,
        )
        evidence = [
            get_ast_annotations(ctx, source.canonical_id, "source"),
            get_ast_annotations(ctx, target.canonical_id, "target"),
        ]

        details: Dict[str, Any] = {
            "protocol": _protocol_details(protocol_entity),
            "subject_kind": subject_kind,
            "subject_index": subject_index,
            "subject_name": subject_name,
            "source_annotation": source_annotation,
            "target_annotation": target_annotation,
        }

        resolution_source = "annotation" if target_annotation else None
        resolution_input = target_annotation
        if target_annotation:
            details["resolution_source"] = "annotation"
        else:
            inference = infer_signature_target_reference(
                target,
                subject_kind=subject_kind,
                subject_index=subject_index,
                entities=ctx.target_index.all_sorted,
            )
            if inference is None:
                details["reason"] = (
                    "missing target annotation on the required signature slot"
                )
                details["failure_reason"] = "missing_target_annotation"
                return _build_rule_result(
                    rule,
                    source,
                    target,
                    match,
                    "FAILED",
                    details,
                    tuple(evidence),
                )
            details["resolution_source"] = "local_ast_fallback"
            details["inference_kind"] = inference.inference_kind
            if inference.reference is None:
                details["reason"] = "ambiguous inferred target reference"
                details["failure_reason"] = (
                    inference.failure_reason or "ambiguous_or_missing"
                )
                return _build_rule_result(
                    rule,
                    source,
                    target,
                    match,
                    "FAILED",
                    details,
                    tuple(evidence),
                )
            resolution_source = "local_ast_fallback"
            resolution_input = inference.reference
            details["inferred_target_reference"] = inference.reference

        resolution = resolve_reference(
            str(resolution_input),
            context_entity=target,
            entities=ctx.target_index.all_sorted,
        )
        details["resolution_source"] = resolution_source
        details["resolved_target_annotation"] = resolution.normalized
        if resolution.entity is None:
            details["reason"] = (
                "unsupported target annotation shape"
                if resolution.reason == "unsupported_reference_shape"
                else "unresolved target annotation"
            )
            details["failure_reason"] = (
                resolution.reason or "unresolved_target_annotation"
            )
            return _build_rule_result(
                rule,
                source,
                target,
                match,
                "FAILED",
                details,
                tuple(evidence),
            )

        details["resolved_target"] = {
            "entity_id": resolution.entity.canonical_id,
            "module_path": resolution.entity.module_path,
            "qualname": resolution.entity.qualname,
            "name": resolution.entity.name,
        }

        mode = str(rule.params.get("signature_mode", "compatible")).lower()
        enforce_method_kind = bool(rule.params.get("enforce_method_kind", True))
        return_annotation = str(rule.params.get("return_annotation", "warning")).lower()
        (
            hard_errors,
            signature_errors,
            attribute_errors,
            return_warnings,
            method_evidence,
            missing_methods,
            required_methods,
            target_methods,
            missing_attributes,
            required_attributes,
            target_attributes,
        ) = _evaluate_protocol_against_class(
            protocol_entity=protocol_entity,
            target_class=resolution.entity,
            ctx=ctx,
            mode=mode,
            enforce_method_kind=enforce_method_kind,
            return_annotation=return_annotation,
        )
        evidence.extend(method_evidence)

        status: RuleStatus = "FAILED" if hard_errors else "OK"
        details.update(
            {
                "reason": (
                    "Protocol requirement satisfied for annotated role."
                    if not hard_errors
                    else "; ".join(hard_errors)
                ),
                "failure_reason": None if not hard_errors else "protocol_mismatch",
                "signature_errors": signature_errors,
                "attribute_errors": attribute_errors,
                "return_warnings": return_warnings,
                "missing_methods": missing_methods,
                "missing_attributes": missing_attributes,
                "required_methods": required_methods,
                "required_attributes": required_attributes,
                "target_methods": target_methods,
                "target_attributes": target_attributes,
                "signature_mode": mode,
                "enforce_method_kind": enforce_method_kind,
                "return_annotation": return_annotation,
            }
        )
        return _build_rule_result(
            rule,
            source,
            target,
            match,
            status,
            details,
            tuple(evidence),
        )


__all__ = ["ProtocolConformanceEvaluator"]
