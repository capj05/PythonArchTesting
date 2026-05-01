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


_SIGNATURE_KEY_PREFIXES = ("p", "a", "v", "k", "w", "d", "kd")


def parse_signature_key(key: str) -> dict[str, int] | None:
    """Parse a `signature_key_from_info` string into its component counts."""
    if key == "-":
        return None
    parsed: dict[str, int] = {}
    for token in key.split("-"):
        if token.startswith("kd"):
            prefix, value = "kd", token[2:]
        elif token and token[0] in {"p", "a", "v", "k", "w", "d"}:
            prefix, value = token[0], token[1:]
        else:
            return None
        try:
            parsed[prefix] = int(value)
        except ValueError:
            return None
    if not all(prefix in parsed for prefix in _SIGNATURE_KEY_PREFIXES):
        return None
    return parsed


def is_extras_only_divergence(source_key: str, target_key: str) -> bool:
    """
    True iff the only divergence between the two signatures is that the target
    has additional optional parameters (vararg / kwarg presence permitted).

    Required positional and required kw-only counts must match. Total positional
    and kw-only counts in the target must be >= source. ``vararg``/``kwarg``
    presence flags must be >= source (target may add but not drop them).
    """
    source = parse_signature_key(source_key)
    target = parse_signature_key(target_key)
    if source is None or target is None:
        return False
    src_required_pos = (source["p"] + source["a"]) - source["d"]
    tgt_required_pos = (target["p"] + target["a"]) - target["d"]
    if src_required_pos != tgt_required_pos:
        return False
    src_required_kw = source["k"] - source["kd"]
    tgt_required_kw = target["k"] - target["kd"]
    if src_required_kw != tgt_required_kw:
        return False
    if (source["p"] + source["a"]) > (target["p"] + target["a"]):
        return False
    if source["k"] > target["k"]:
        return False
    if source["v"] > target["v"]:
        return False
    if source["w"] > target["w"]:
        return False
    return True


def is_param_rename_only_divergence(source_key: str, target_key: str) -> bool:
    """
    True iff source and target signatures share identical structural counts
    (positional/keyword arity, defaults, vararg/kwarg presence). ``signature_key``
    encodes counts only, so a parameter rename leaves every component equal.
    Acts as an admission gate for re-gating LOW_CONFIDENCE matches; the
    evaluator still issues the real verdict against the actual parameter names.
    """
    source = parse_signature_key(source_key)
    target = parse_signature_key(target_key)
    if source is None or target is None:
        return False
    return all(
        source[component] == target[component] for component in _SIGNATURE_KEY_PREFIXES
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
