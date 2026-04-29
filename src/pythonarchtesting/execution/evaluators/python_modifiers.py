from __future__ import annotations

import ast
from typing import Any

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult
from pythonarchtesting.protocols.entity_lookup import ProtocolEntityLookup
from pythonarchtesting.protocols.reference_resolution import normalize_reference

from .messages import _build_rule_result

_ABSTRACT_DECORATORS = frozenset(
    {
        "abstractmethod",
        "abc.abstractmethod",
        "abstractclassmethod",
        "abc.abstractclassmethod",
        "abstractstaticmethod",
        "abc.abstractstaticmethod",
        "abstractproperty",
        "abc.abstractproperty",
    }
)
_FINAL_DECORATORS = frozenset({"final", "typing.final", "typing_extensions.final"})


def _decorator_ref_name(node: ast.AST) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    try:
        return ast.unparse(target)
    except Exception:
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, ast.Attribute):
            return target.attr
    return None


def _normalized_decorator_refs(
    entity: Entity,
    lookup: ProtocolEntityLookup,
) -> tuple[str, ...]:
    refs = entity.surface_meta.get("decorator_refs")
    if isinstance(refs, (list, tuple)):
        return tuple(str(ref) for ref in refs if str(ref))

    node = entity.extras.get("ast_node")
    decorator_list = getattr(node, "decorator_list", None)
    if not isinstance(decorator_list, list):
        return ()

    aliases = lookup.import_aliases(entity.module_path)
    resolved: list[str] = []
    for decorator in decorator_list:
        ref_name = _decorator_ref_name(decorator)
        if not ref_name:
            continue
        normalized, _ = normalize_reference(
            ref_name,
            module_path=entity.module_path,
            aliases=aliases,
        )
        resolved.append(normalized or ref_name)
    return tuple(resolved)


def _decorator_matches(refs: tuple[str, ...], accepted: frozenset[str]) -> bool:
    for ref in refs:
        if ref in accepted:
            return True
    return False


def _direct_declared_methods(
    class_entity: Entity,
    lookup: ProtocolEntityLookup,
) -> tuple[Entity, ...]:
    prefix = f"{class_entity.qualname}."
    methods = [
        candidate
        for candidate in lookup.entities
        if candidate.kind == "method"
        and candidate.module_path == class_entity.module_path
        and candidate.qualname.startswith(prefix)
        and "." not in candidate.qualname[len(prefix) :]
    ]
    methods.sort(key=lambda method: (method.name, method.qualname, method.lineno))
    return tuple(methods)


def _declared_abstract_method_names(
    class_entity: Entity,
    lookup: ProtocolEntityLookup,
) -> set[str]:
    return {
        method.name
        for method in _direct_declared_methods(class_entity, lookup)
        if _decorator_matches(
            _normalized_decorator_refs(method, lookup), _ABSTRACT_DECORATORS
        )
    }


def _declared_concrete_method_names(
    class_entity: Entity,
    lookup: ProtocolEntityLookup,
) -> set[str]:
    return {
        method.name
        for method in _direct_declared_methods(class_entity, lookup)
        if not _decorator_matches(
            _normalized_decorator_refs(method, lookup), _ABSTRACT_DECORATORS
        )
    }


def _direct_local_base_classes(
    class_entity: Entity,
    lookup: ProtocolEntityLookup,
) -> tuple[Entity, ...]:
    return lookup.resolved_bases(class_entity)


def _unresolved_abstract_names(
    class_entity: Entity,
    lookup: ProtocolEntityLookup,
    visited: set[str] | None = None,
) -> set[str]:
    if visited is None:
        visited = set()
    if class_entity.canonical_id in visited:
        return set()
    visited.add(class_entity.canonical_id)

    inherited_unresolved: set[str] = set()
    for base_entity in _direct_local_base_classes(class_entity, lookup):
        inherited_unresolved.update(
            _unresolved_abstract_names(base_entity, lookup, visited)
        )

    declared_abstract = _declared_abstract_method_names(class_entity, lookup)
    declared_concrete = _declared_concrete_method_names(class_entity, lookup)
    return (inherited_unresolved | declared_abstract) - declared_concrete


def _class_payload(entity: Entity) -> dict[str, Any]:
    return {
        "entity_id": entity.canonical_id,
        "module_path": entity.module_path,
        "qualname": entity.qualname,
        "name": entity.name,
    }


def _method_payload(entity: Entity) -> dict[str, Any]:
    return {
        "entity_id": entity.canonical_id,
        "module_path": entity.module_path,
        "qualname": entity.qualname,
        "name": entity.name,
        "method_kind": entity.surface_meta.get("method_kind", "instance"),
        "is_property": bool(entity.surface_meta.get("property")),
    }


def _modifier_details(
    class_entity: Entity,
    lookup: ProtocolEntityLookup,
) -> dict[str, Any]:
    declared_abstract_names = sorted(
        _declared_abstract_method_names(class_entity, lookup)
    )
    declared_concrete_names = sorted(
        _declared_concrete_method_names(class_entity, lookup)
    )
    unresolved_abstract_names = sorted(
        _unresolved_abstract_names(class_entity, lookup, set())
    )
    local_base_classes = sorted(
        f"{base_entity.module_path}.{base_entity.qualname}"
        for base_entity in _direct_local_base_classes(class_entity, lookup)
    )
    return {
        "declared_abstract_names": declared_abstract_names,
        "declared_concrete_names": declared_concrete_names,
        "unresolved_abstract_names": unresolved_abstract_names,
        "local_base_classes": local_base_classes,
    }


def _is_final_class(
    class_entity: Entity,
    lookup: ProtocolEntityLookup,
) -> tuple[bool, str | None, tuple[str, ...]]:
    normalized_decorators = _normalized_decorator_refs(class_entity, lookup)
    for decorator_ref in normalized_decorators:
        if decorator_ref in _FINAL_DECORATORS:
            return True, decorator_ref, normalized_decorators
    return False, None, normalized_decorators


def _is_abstract_method(
    method_entity: Entity,
    lookup: ProtocolEntityLookup,
) -> tuple[bool, str | None, tuple[str, ...]]:
    normalized_decorators = _normalized_decorator_refs(method_entity, lookup)
    for decorator_ref in normalized_decorators:
        if decorator_ref in _ABSTRACT_DECORATORS:
            return True, decorator_ref, normalized_decorators
    return False, None, normalized_decorators


def _is_final_method(
    method_entity: Entity,
    lookup: ProtocolEntityLookup,
) -> tuple[bool, str | None, tuple[str, ...]]:
    normalized_decorators = _normalized_decorator_refs(method_entity, lookup)
    for decorator_ref in normalized_decorators:
        if decorator_ref in _FINAL_DECORATORS:
            return True, decorator_ref, normalized_decorators
    return False, None, normalized_decorators


_NEGATIVE_MODIFIER_KINDS = frozenset(
    {"non_final_class", "non_abstract_method", "non_final_method"}
)


def _negative_modifier_result_details(
    *,
    modifier_kind: str,
    observed: bool,
    observed_label: str,
    decorator_field: str,
    recognized_decorator: str | None,
    normalized_decorators: tuple[str, ...],
    target_payload: dict[str, Any],
    target_payload_field: str,
    target_subject: str,
) -> dict[str, Any]:
    decorator_kind_word = "abstract" if observed_label.startswith("abstract") else "final"
    reason = (
        f"target {target_subject} is decorated with a recognized {decorator_kind_word} decorator"
        if observed
        else f"target {target_subject} is not decorated with a recognized {decorator_kind_word} decorator"
    )
    failure_reason = (
        f"forbidden_{observed_label}_present"
        if observed
        else f"forbidden_{observed_label}_absent"
    )
    return {
        "reason": reason,
        "modifier_kind": modifier_kind,
        "modifier_polarity": "negative",
        "failure_reason": failure_reason,
        "normalized_decorators": list(normalized_decorators),
        decorator_field: recognized_decorator,
        target_payload_field: target_payload,
    }


class PythonModifierEvaluator:
    """Evaluator for Python-native class and method modifier rules."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        lookup = ProtocolEntityLookup.from_entities(ctx.target_index.all_sorted)
        modifier_kind = str(rule.params.get("modifier_kind", "")).lower()

        if modifier_kind in {
            "abstract_method",
            "final_method",
            "non_abstract_method",
            "non_final_method",
        }:
            if target.kind != "method":
                details: dict[str, Any] = {
                    "reason": (
                        f"matched target kind '{target.kind}' "
                        "does not support method modifier checks"
                    ),
                    "modifier_kind": modifier_kind,
                }
                if modifier_kind in _NEGATIVE_MODIFIER_KINDS:
                    details["modifier_polarity"] = "negative"
                    details["failure_reason"] = "invalid_target_kind"
                return _build_rule_result(
                    rule,
                    source,
                    target,
                    match,
                    "FAILED",
                    details,
                    (),
                )

            if modifier_kind == "abstract_method":
                is_abstract, recognized_abstract_decorator, normalized_decorators = (
                    _is_abstract_method(target, lookup)
                )
                abstract_details: dict[str, Any] = {
                    "reason": (
                        "target method is decorated with a recognized abstract decorator"
                        if is_abstract
                        else "target method is not decorated with a recognized abstract decorator"
                    ),
                    "modifier_kind": modifier_kind,
                    "normalized_decorators": list(normalized_decorators),
                    "recognized_abstract_decorator": recognized_abstract_decorator,
                    "target_method": _method_payload(target),
                }
                return _build_rule_result(
                    rule,
                    source,
                    target,
                    match,
                    "OK" if is_abstract else "FAILED",
                    abstract_details,
                    (),
                )

            if modifier_kind == "non_abstract_method":
                is_abstract, recognized_abstract_decorator, normalized_decorators = (
                    _is_abstract_method(target, lookup)
                )
                non_abstract_details = _negative_modifier_result_details(
                    modifier_kind=modifier_kind,
                    observed=is_abstract,
                    observed_label="abstract_method",
                    decorator_field="recognized_abstract_decorator",
                    recognized_decorator=recognized_abstract_decorator,
                    normalized_decorators=normalized_decorators,
                    target_payload=_method_payload(target),
                    target_payload_field="target_method",
                    target_subject="method",
                )
                return _build_rule_result(
                    rule,
                    source,
                    target,
                    match,
                    "FAILED" if is_abstract else "OK",
                    non_abstract_details,
                    (),
                )

            if modifier_kind == "non_final_method":
                is_final, recognized_final_decorator, normalized_decorators = (
                    _is_final_method(target, lookup)
                )
                non_final_method_details = _negative_modifier_result_details(
                    modifier_kind=modifier_kind,
                    observed=is_final,
                    observed_label="final_method",
                    decorator_field="recognized_final_decorator",
                    recognized_decorator=recognized_final_decorator,
                    normalized_decorators=normalized_decorators,
                    target_payload=_method_payload(target),
                    target_payload_field="target_method",
                    target_subject="method",
                )
                return _build_rule_result(
                    rule,
                    source,
                    target,
                    match,
                    "FAILED" if is_final else "OK",
                    non_final_method_details,
                    (),
                )

            is_final, recognized_final_decorator, normalized_decorators = (
                _is_final_method(target, lookup)
            )
            final_details: dict[str, Any] = {
                "reason": (
                    "target method is decorated with a recognized final decorator"
                    if is_final
                    else "target method is not decorated with a recognized final decorator"
                ),
                "modifier_kind": modifier_kind,
                "normalized_decorators": list(normalized_decorators),
                "recognized_final_decorator": recognized_final_decorator,
                "target_method": _method_payload(target),
            }
            return _build_rule_result(
                rule,
                source,
                target,
                match,
                "OK" if is_final else "FAILED",
                final_details,
                (),
            )

        if target.kind != "class":
            details: dict[str, Any] = {
                "reason": (
                    f"matched target kind '{target.kind}' "
                    "does not support class modifier checks"
                ),
                "modifier_kind": modifier_kind,
            }
            if modifier_kind in _NEGATIVE_MODIFIER_KINDS:
                details["modifier_polarity"] = "negative"
                details["failure_reason"] = "invalid_target_kind"
            return _build_rule_result(
                rule,
                source,
                target,
                match,
                "FAILED",
                details,
                (),
            )

        if modifier_kind in {"abstract_class", "concrete_class"}:
            details = _modifier_details(target, lookup)
            details["modifier_kind"] = modifier_kind
            is_abstract = bool(details["unresolved_abstract_names"])
            if modifier_kind == "abstract_class":
                details["reason"] = (
                    "target class has unresolved abstract members"
                    if is_abstract
                    else "target class has no unresolved abstract members"
                )
                status: RuleStatus = "OK" if is_abstract else "FAILED"
            else:
                details["reason"] = (
                    "target class has no unresolved abstract members"
                    if not is_abstract
                    else "target class has unresolved abstract members"
                )
                status = "OK" if not is_abstract else "FAILED"
            return _build_rule_result(rule, source, target, match, status, details, ())

        if modifier_kind == "final_class":
            is_final, recognized_final_decorator, normalized_decorators = (
                _is_final_class(target, lookup)
            )
            final_details: dict[str, Any] = {
                "reason": (
                    "target class is decorated with a recognized final decorator"
                    if is_final
                    else "target class is not decorated with a recognized final decorator"
                ),
                "modifier_kind": modifier_kind,
                "normalized_decorators": list(normalized_decorators),
                "recognized_final_decorator": recognized_final_decorator,
                "target_class": _class_payload(target),
            }
            return _build_rule_result(
                rule,
                source,
                target,
                match,
                "OK" if is_final else "FAILED",
                final_details,
                (),
            )

        if modifier_kind == "non_final_class":
            is_final, recognized_final_decorator, normalized_decorators = (
                _is_final_class(target, lookup)
            )
            non_final_class_details = _negative_modifier_result_details(
                modifier_kind=modifier_kind,
                observed=is_final,
                observed_label="final_class",
                decorator_field="recognized_final_decorator",
                recognized_decorator=recognized_final_decorator,
                normalized_decorators=normalized_decorators,
                target_payload=_class_payload(target),
                target_payload_field="target_class",
                target_subject="class",
            )
            return _build_rule_result(
                rule,
                source,
                target,
                match,
                "FAILED" if is_final else "OK",
                non_final_class_details,
                (),
            )

        raise ValueError(f"Unsupported python modifier kind: {modifier_kind}")


__all__ = ["PythonModifierEvaluator"]
