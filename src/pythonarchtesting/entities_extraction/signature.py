from __future__ import annotations

import ast
from typing import Any, Optional

from pythonarchtesting.entities import SignatureInfo
from pythonarchtesting.protocols.signature_slots import signature_slots
from pythonarchtesting.protocols.type_expr import unwrap_annotated_annotation_text


def _annotation_strings(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    skip_first_arg: bool = False,
) -> dict[str, Any]:
    entries: list[dict[str, Optional[str]]] = []
    vararg_name = fn.args.vararg.arg if fn.args.vararg is not None else None
    kwarg_name = fn.args.kwarg.arg if fn.args.kwarg is not None else None
    for slot in signature_slots(fn):
        if slot.subject_kind != "param":
            continue
        arg = slot.annotation_node
        if not isinstance(arg, ast.arg):
            continue
        name = arg.arg
        if name == vararg_name:
            name = f"*{name}"
        elif name == kwarg_name:
            name = f"**{name}"
        entries.append(
            {
                "name": name,
                "annotation": unwrap_annotated_annotation_text(arg.annotation) or None,
            }
        )
    return_annotation = unwrap_annotated_annotation_text(fn.returns) or None
    entries_for_has_all = entries
    if skip_first_arg and entries and entries[0]["name"] in {"self", "cls"}:
        entries_for_has_all = entries[1:]
    has_all = all(item["annotation"] is not None for item in entries_for_has_all) and (
        return_annotation is not None
    )
    return {"args": entries, "return": return_annotation, "has_all": has_all}


def _line_text_from_source(file_text: str, lineno: int) -> Optional[str]:
    if lineno <= 0:
        return None
    lines = file_text.splitlines()
    if lineno > len(lines):
        return None
    return lines[lineno - 1]


def signature_info_from_ast(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> SignatureInfo:
    posonly = len(fn.args.posonlyargs)
    pos = len(fn.args.args)
    vararg = fn.args.vararg is not None
    kwonly = len(fn.args.kwonlyargs)
    kwarg = fn.args.kwarg is not None
    defaults = len(fn.args.defaults)
    kw_defaults = sum(1 for d in fn.args.kw_defaults if d is not None)
    return SignatureInfo(
        posonly=posonly,
        pos=pos,
        vararg=vararg,
        kwonly=kwonly,
        kwarg=kwarg,
        defaults=defaults,
        kw_defaults=kw_defaults,
    )


__all__ = ["signature_info_from_ast"]
