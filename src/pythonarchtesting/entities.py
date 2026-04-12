from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

Role = Literal["source", "target"]
EntityKind = Literal["module", "class", "function", "method"]


@dataclass(frozen=True)
class SignatureInfo:
    posonly: int
    pos: int
    vararg: bool
    kwonly: int
    kwarg: bool
    defaults: int
    kw_defaults: int


@dataclass(frozen=True)
class AnnotationDeclaration:
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    unsupported: list[dict[str, Any]] = field(default_factory=list)
    raw: str = ""
    lineno: int = 0
    col: int = 0
    order: int = 0
    container: str = ""
    base_annotation: str = ""
    surface: str = "body"
    subject_kind: str = ""
    subject_index: int = -1
    subject_name: str = ""


@dataclass(frozen=True)
class DeclarationEntry:
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    unsupported: list[dict[str, Any]] = field(default_factory=list)
    lineno: int = 0
    col: int = 0
    order: int = 0
    raw: str = ""
    base_annotation: str = ""
    container: str = ""
    surface: str = "body"
    subject_kind: str = ""
    subject_index: int = -1
    subject_name: str = ""


@dataclass(frozen=True)
class Entity:
    role: Role
    kind: EntityKind
    root_label: str
    module_path: str
    qualname: str
    name: str
    filepath_rel: str
    lineno: int
    signature: SignatureInfo | None
    signature_key: str
    ast_fingerprint: str
    source_hash: str
    doc_hash: str | None
    decorators_meta: dict[str, Any]
    canonical_id: str
    annotation_declarations: list[AnnotationDeclaration] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def surface_meta(self) -> dict[str, Any]:
        """Canonical non-rule AST surface metadata for this entity."""
        return self.decorators_meta


@dataclass
class EntityIndex:
    by_core: dict[str, list[Entity]]
    by_name: dict[tuple[str, str], list[Entity]]
    by_sig: dict[tuple[str, str], list[Entity]]
    by_fp: dict[tuple[str, str], list[Entity]]
    all_sorted: list[Entity]


def normalize_docstring(value: str | None) -> str:
    if value is None:
        return ""
    text = value.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def signature_key_from_info(signature: SignatureInfo | None) -> str:
    if signature is None:
        return "-"
    return (
        f"p{signature.posonly}-a{signature.pos}-v{1 if signature.vararg else 0}-"
        f"k{signature.kwonly}-w{1 if signature.kwarg else 0}-"
        f"d{signature.defaults}-kd{signature.kw_defaults}"
    )


def build_canonical_id(
    role: Role,
    root_label: str,
    module_path: str,
    qualname: str,
    kind: EntityKind,
    signature_key: str,
) -> str:
    return f"{role}:{root_label}:{module_path}:{qualname}:{kind}:{signature_key}"


def _sort_key(entity: Entity) -> tuple[Any, ...]:
    return (
        entity.module_path,
        entity.qualname,
        entity.kind,
        entity.signature_key,
        entity.filepath_rel,
        entity.lineno,
        entity.canonical_id,
    )


def sort_entities(entities: Iterable[Entity]) -> list[Entity]:
    return sorted(list(entities), key=_sort_key)


def _sort_index_lists(index: dict[Any, list[Entity]]) -> None:
    for key in list(index.keys()):
        index[key] = sort_entities(index[key])


def build_entity_index(entities: Iterable[Entity]) -> EntityIndex:
    by_core: dict[str, list[Entity]] = {}
    by_name: dict[tuple[str, str], list[Entity]] = {}
    by_sig: dict[tuple[str, str], list[Entity]] = {}
    by_fp: dict[tuple[str, str], list[Entity]] = {}

    for entity in entities:
        core_key = (
            f"{entity.module_path}:{entity.qualname}:"
            f"{entity.kind}:{entity.signature_key}"
        )
        by_core.setdefault(core_key, []).append(entity)
        by_name.setdefault((entity.kind, entity.name), []).append(entity)
        by_sig.setdefault((entity.kind, entity.signature_key), []).append(entity)
        if entity.ast_fingerprint:
            by_fp.setdefault((entity.kind, entity.ast_fingerprint), []).append(entity)

    _sort_index_lists(by_core)
    _sort_index_lists(by_name)
    _sort_index_lists(by_sig)
    _sort_index_lists(by_fp)

    all_sorted = sort_entities(list(entities))
    return EntityIndex(
        by_core=by_core,
        by_name=by_name,
        by_sig=by_sig,
        by_fp=by_fp,
        all_sorted=all_sorted,
    )


__all__ = [
    "Role",
    "EntityKind",
    "SignatureInfo",
    "AnnotationDeclaration",
    "DeclarationEntry",
    "Entity",
    "EntityIndex",
    "normalize_docstring",
    "hash_text",
    "signature_key_from_info",
    "build_canonical_id",
    "sort_entities",
    "build_entity_index",
]
