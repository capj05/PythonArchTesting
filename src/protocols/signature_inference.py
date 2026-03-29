from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Sequence

from src.entities import Entity
from src.protocols.reference_resolution import resolve_reference


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
    resolution = resolve_reference(reference, context_entity=context_entity, entities=entities)
    if resolution.entity is None:
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


def _collect_return_references(
    statements: list[ast.stmt] | tuple[ast.stmt, ...],
    *,
    context_entity: Entity,
    entities: Sequence[Entity],
    collected: list[SignatureInferenceResult],
) -> None:
    for stmt in statements:
        if isinstance(
            stmt,
            (
                ast.If,
                ast.Try,
                ast.Match,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.With,
                ast.AsyncWith,
            ),
        ):
            break
        if isinstance(stmt, ast.Return):
            reference = _resolved_constructor_reference(
                stmt.value, context_entity=context_entity, entities=entities
            )
            if reference is not None:
                collected.append(
                    SignatureInferenceResult(
                        reference=reference,
                        inference_kind="return_direct_constructor",
                    )
                )
            break


def _return_reference(
    entity: Entity, *, entities: Sequence[Entity]
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
    )
    if not collected:
        return None

    references = {item.reference for item in collected if item.reference}
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
