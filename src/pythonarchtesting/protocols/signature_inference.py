from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Sequence

from pythonarchtesting.entities import Entity
from pythonarchtesting.protocols.reference_resolution import resolve_reference


@dataclass(frozen=True)
class SignatureInferenceResult:
    reference: str | None
    inference_kind: str | None = None
    failure_reason: str | None = None


def _unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    return ast.unparse(node)


def _constructor_reference(node: ast.AST | None) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    if not isinstance(node.func, (ast.Name, ast.Subscript)):
        return None
    reference = _unparse(node.func).strip()
    return reference or None


def _resolved_constructor_reference(
    node: ast.AST | None, *, context_entity: Entity, entities: Sequence[Entity]
) -> str | None:
    reference = _constructor_reference(node)
    if reference is None:
        return None
    resolution = resolve_reference(
        reference, context_entity=context_entity, entities=entities
    )
    if resolution.entity is None or resolution.entity.kind != "class":
        return None
    return reference


def _param_default_reference(
    entity: Entity, *, subject_index: int, entities: Sequence[Entity]
) -> SignatureInferenceResult | None:
    node = entity.extras.get("ast_node")
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None

    positional = list(node.args.posonlyargs) + list(node.args.args)
    positional_defaults = [None] * (len(positional) - len(node.args.defaults)) + list(
        node.args.defaults
    )
    entries: list[tuple[ast.arg, ast.expr | None]] = list(
        zip(positional, positional_defaults)
    )
    entries.extend(zip(node.args.kwonlyargs, node.args.kw_defaults))

    visible_index = 0
    for idx, (arg, default) in enumerate(entries):
        if idx == 0 and arg.arg in {"self", "cls"}:
            continue
        if visible_index == subject_index:
            reference = _resolved_constructor_reference(
                default, context_entity=entity, entities=entities
            )
            if reference is None:
                return None
            return SignatureInferenceResult(
                reference=reference,
                inference_kind="param_default_constructor",
            )
        visible_index += 1
    return None


def _same_module_helper(
    helper_name: str, *, context_entity: Entity, entities: Sequence[Entity]
) -> Entity | None:
    matches = [
        entity
        for entity in entities
        if entity.kind == "function"
        and entity.module_path == context_entity.module_path
        and entity.name == helper_name
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def _assigned_constructor_references(
    statements: list[ast.stmt] | tuple[ast.stmt, ...],
    *,
    context_entity: Entity,
    entities: Sequence[Entity],
) -> dict[str, str]:
    assigned: dict[str, str] = {}
    for stmt in statements:
        if isinstance(stmt, ast.Assign):
            targets = [
                target for target in stmt.targets if isinstance(target, ast.Name)
            ]
            if len(targets) != 1:
                continue
            reference = _resolved_constructor_reference(
                stmt.value, context_entity=context_entity, entities=entities
            )
            if reference is None:
                assigned.pop(targets[0].id, None)
            else:
                assigned[targets[0].id] = reference
            continue
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            reference = _resolved_constructor_reference(
                stmt.value, context_entity=context_entity, entities=entities
            )
            if reference is None:
                assigned.pop(stmt.target.id, None)
            else:
                assigned[stmt.target.id] = reference
    return assigned


def _return_expression_reference(
    expr: ast.AST | None,
    *,
    context_entity: Entity,
    entities: Sequence[Entity],
    assigned_locals: dict[str, str],
    helper_hops_remaining: int,
    helper_stack: tuple[str, ...],
) -> SignatureInferenceResult | None:
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name):
        helper = _same_module_helper(
            expr.func.id, context_entity=context_entity, entities=entities
        )
        if helper is not None and helper.canonical_id in helper_stack:
            return SignatureInferenceResult(
                reference=None,
                inference_kind="return_same_module_helper_cycle",
                failure_reason="ambiguous_or_missing",
            )

    direct_reference = _resolved_constructor_reference(
        expr, context_entity=context_entity, entities=entities
    )
    if direct_reference is not None:
        return SignatureInferenceResult(
            reference=direct_reference,
            inference_kind="return_direct_constructor",
        )

    if isinstance(expr, ast.Name):
        assigned_reference = assigned_locals.get(expr.id)
        if assigned_reference is None:
            return None
        return SignatureInferenceResult(
            reference=assigned_reference,
            inference_kind="return_assigned_local_constructor",
        )

    if (
        helper_hops_remaining > 0
        and isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
    ):
        helper = _same_module_helper(
            expr.func.id, context_entity=context_entity, entities=entities
        )
        if helper is None:
            return None
        helper_result = _return_reference(
            helper,
            entities=entities,
            helper_hops_remaining=helper_hops_remaining - 1,
            helper_stack=(*helper_stack, helper.canonical_id),
        )
        if helper_result is None:
            return None
        if helper_result.reference is None:
            return helper_result
        return SignatureInferenceResult(
            reference=helper_result.reference,
            inference_kind="return_same_module_helper_constructor",
        )

    return None


def _collect_return_references(
    statements: list[ast.stmt] | tuple[ast.stmt, ...],
    *,
    context_entity: Entity,
    entities: Sequence[Entity],
    collected: list[SignatureInferenceResult],
    helper_hops_remaining: int,
    helper_stack: tuple[str, ...],
) -> None:
    assigned_locals = _assigned_constructor_references(
        statements, context_entity=context_entity, entities=entities
    )
    for stmt in statements:
        if isinstance(stmt, ast.If):
            _collect_return_references(
                stmt.body,
                context_entity=context_entity,
                entities=entities,
                collected=collected,
                helper_hops_remaining=helper_hops_remaining,
                helper_stack=helper_stack,
            )
            _collect_return_references(
                stmt.orelse,
                context_entity=context_entity,
                entities=entities,
                collected=collected,
                helper_hops_remaining=helper_hops_remaining,
                helper_stack=helper_stack,
            )
            continue
        if isinstance(stmt, ast.Try):
            _collect_return_references(
                stmt.body,
                context_entity=context_entity,
                entities=entities,
                collected=collected,
                helper_hops_remaining=helper_hops_remaining,
                helper_stack=helper_stack,
            )
            _collect_return_references(
                stmt.orelse,
                context_entity=context_entity,
                entities=entities,
                collected=collected,
                helper_hops_remaining=helper_hops_remaining,
                helper_stack=helper_stack,
            )
            _collect_return_references(
                stmt.finalbody,
                context_entity=context_entity,
                entities=entities,
                collected=collected,
                helper_hops_remaining=helper_hops_remaining,
                helper_stack=helper_stack,
            )
            for handler in stmt.handlers:
                _collect_return_references(
                    handler.body,
                    context_entity=context_entity,
                    entities=entities,
                    collected=collected,
                    helper_hops_remaining=helper_hops_remaining,
                    helper_stack=helper_stack,
                )
            continue
        if isinstance(stmt, ast.Match):
            for case in stmt.cases:
                _collect_return_references(
                    case.body,
                    context_entity=context_entity,
                    entities=entities,
                    collected=collected,
                    helper_hops_remaining=helper_hops_remaining,
                    helper_stack=helper_stack,
                )
            continue
        if isinstance(
            stmt, (ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith)
        ):
            _collect_return_references(
                stmt.body,
                context_entity=context_entity,
                entities=entities,
                collected=collected,
                helper_hops_remaining=helper_hops_remaining,
                helper_stack=helper_stack,
            )
            if hasattr(stmt, "orelse"):
                _collect_return_references(
                    stmt.orelse,
                    context_entity=context_entity,
                    entities=entities,
                    collected=collected,
                    helper_hops_remaining=helper_hops_remaining,
                    helper_stack=helper_stack,
                )
            continue
        if isinstance(stmt, ast.Return):
            result = _return_expression_reference(
                stmt.value,
                context_entity=context_entity,
                entities=entities,
                assigned_locals=assigned_locals,
                helper_hops_remaining=helper_hops_remaining,
                helper_stack=helper_stack,
            )
            if result is not None:
                collected.append(result)
            continue


def _return_reference(
    entity: Entity,
    *,
    entities: Sequence[Entity],
    helper_hops_remaining: int = 1,
    helper_stack: tuple[str, ...] = (),
) -> SignatureInferenceResult | None:
    node = entity.extras.get("ast_node")
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None

    collected: list[SignatureInferenceResult] = []
    _collect_return_references(
        node.body,
        context_entity=entity,
        entities=entities,
        collected=collected,
        helper_hops_remaining=helper_hops_remaining,
        helper_stack=helper_stack or (entity.canonical_id,),
    )
    if not collected:
        return None

    if any(
        item.inference_kind == "return_same_module_helper_cycle" for item in collected
    ):
        return SignatureInferenceResult(
            reference=None,
            inference_kind="return_same_module_helper_cycle",
            failure_reason="ambiguous_or_missing",
        )

    references = {item.reference for item in collected if item.reference is not None}
    if len(references) != 1:
        return SignatureInferenceResult(
            reference=None,
            inference_kind="return_conflicting_local_constructors",
            failure_reason="ambiguous_or_missing",
        )

    reference = next(iter(references))
    first = next(item for item in collected if item.reference == reference)
    return SignatureInferenceResult(
        reference=reference,
        inference_kind=first.inference_kind,
    )


def infer_signature_target_reference(
    entity: Entity, *, subject_kind: str, subject_index: int, entities: Sequence[Entity]
) -> SignatureInferenceResult | None:
    if subject_kind == "return":
        return _return_reference(entity, entities=entities)
    if subject_kind == "param":
        return _param_default_reference(
            entity, subject_index=subject_index, entities=entities
        )
    return None


__all__ = ["SignatureInferenceResult", "infer_signature_target_reference"]
