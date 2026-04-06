from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from src.entities import Entity


@dataclass(frozen=True)
class SignatureSlot:
    annotation_node: ast.arg | ast.expr | None
    subject_kind: str
    subject_index: int
    subject_name: str


@dataclass(frozen=True)
class _ResolvedSignatureSlot:
    annotation_text: str | None
    subject_kind: str
    subject_index: int
    subject_name: str


def _slot_index(idx: int, name: str, visible_index: int) -> int:
    if idx == 0 and name in {"self", "cls"}:
        return -1
    return visible_index


def _annotation_slots(
    annotations: dict[str, Any] | Any,
) -> list[_ResolvedSignatureSlot]:
    if not isinstance(annotations, dict):
        return []

    slots: list[_ResolvedSignatureSlot] = []
    visible_index = 0
    for idx, entry in enumerate(list(annotations.get("args") or [])):
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "")
        subject_index = _slot_index(idx, name, visible_index)
        annotation = entry.get("annotation")
        slots.append(
            _ResolvedSignatureSlot(
                annotation_text=str(annotation) if annotation is not None else None,
                subject_kind="param",
                subject_index=subject_index,
                subject_name=name,
            )
        )
        if subject_index != -1:
            visible_index += 1

    return_annotation = annotations.get("return")
    slots.append(
        _ResolvedSignatureSlot(
            annotation_text=(
                str(return_annotation) if return_annotation is not None else None
            ),
            subject_kind="return",
            subject_index=-1,
            subject_name="return",
        )
    )
    return slots


def signature_slots(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[SignatureSlot]:
    slots: list[SignatureSlot] = []
    visible_index = 0
    parameter_nodes: list[ast.arg] = [*node.args.posonlyargs, *node.args.args]
    if node.args.vararg is not None:
        parameter_nodes.append(node.args.vararg)
    parameter_nodes.extend(node.args.kwonlyargs)
    if node.args.kwarg is not None:
        parameter_nodes.append(node.args.kwarg)

    for idx, arg in enumerate(parameter_nodes):
        subject_index = _slot_index(idx, arg.arg, visible_index)
        slots.append(
            SignatureSlot(
                annotation_node=arg,
                subject_kind="param",
                subject_index=subject_index,
                subject_name=arg.arg,
            )
        )
        if subject_index != -1:
            visible_index += 1

    slots.append(
        SignatureSlot(
            annotation_node=node.returns,
            subject_kind="return",
            subject_index=-1,
            subject_name="return",
        )
    )
    return slots


def signature_subject_annotation(
    entity: Entity, *, subject_kind: str, subject_index: int
) -> str | None:
    annotations = entity.extras.get("annotations") or {}
    for slot in _annotation_slots(annotations):
        if slot.subject_kind == subject_kind and slot.subject_index == subject_index:
            return slot.annotation_text
    return None


__all__ = ["SignatureSlot", "signature_slots", "signature_subject_annotation"]
