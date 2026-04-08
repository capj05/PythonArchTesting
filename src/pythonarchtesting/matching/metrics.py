from __future__ import annotations

import re
from typing import List, Mapping

from pythonarchtesting.entities import Entity


def _parts(path: str) -> List[str]:
    return [p for p in path.split(".") if p]


def module_similarity(source_module: str, target_module: str) -> float:
    source_parts = _parts(source_module)
    target_parts = _parts(target_module)
    if not source_parts and not target_parts:
        return 1.0
    if not source_parts or not target_parts:
        return 0.0
    common = 0
    for a, b in zip(source_parts, target_parts):
        if a != b:
            break
        common += 1
    return common / max(len(source_parts), len(target_parts))


def module_distance(source_module: str, target_module: str) -> int:
    source_parts = _parts(source_module)
    target_parts = _parts(target_module)
    common = 0
    for a, b in zip(source_parts, target_parts):
        if a != b:
            break
        common += 1
    return len(source_parts) + len(target_parts) - 2 * common


def ast_similarity(source: Entity, target: Entity) -> float:
    bag_a = _token_bag(source.extras.get("ast_tokens_bag"))
    bag_b = _token_bag(target.extras.get("ast_tokens_bag"))
    if not bag_a or not bag_b:
        return 0.0
    keys = set(bag_a.keys()) | set(bag_b.keys())
    if not keys:
        return 1.0
    intersect = sum(min(bag_a.get(k, 0), bag_b.get(k, 0)) for k in keys)
    union = sum(max(bag_a.get(k, 0), bag_b.get(k, 0)) for k in keys)
    if union == 0:
        return 1.0
    return intersect / union


def _token_bag(value: object) -> dict[str, int] | None:
    if not isinstance(value, Mapping):
        return None
    normalized: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str):
            continue
        try:
            normalized[key] = int(count)
        except (TypeError, ValueError):
            continue
    return normalized


def levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(
                min(
                    prev[j] + 1,
                    curr[j - 1] + 1,
                    prev[j - 1] + cost,
                )
            )
        prev = curr
    return prev[-1]


def name_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    dist = levenshtein_distance(a, b)
    return 1.0 - dist / max(len(a), len(b))


def doc_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    tokens_a = {t for t in re.split(r"\W+", a.lower()) if t}
    tokens_b = {t for t in re.split(r"\W+", b.lower()) if t}
    if not tokens_a and not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    return len(tokens_a & tokens_b) / len(union)


def class_name_from_qualname(qualname: str) -> str:
    if "." not in qualname:
        return ""
    return qualname.rsplit(".", 1)[0].split(".")[-1]


def method_first_param_mismatch(source: Entity, target: Entity) -> bool:
    if source.kind != "method" or target.kind != "method":
        return False
    if source.signature is None or target.signature is None:
        return False
    if source.signature_key == target.signature_key:
        return False

    a = source.signature
    b = target.signature
    if a.posonly != b.posonly:
        return False
    if a.vararg != b.vararg:
        return False
    if a.kwonly != b.kwonly:
        return False
    if a.kwarg != b.kwarg:
        return False
    if a.defaults != b.defaults:
        return False
    if a.kw_defaults != b.kw_defaults:
        return False
    if abs(a.pos - b.pos) != 1:
        return False
    return True


__all__ = [
    "module_similarity",
    "module_distance",
    "ast_similarity",
    "levenshtein_distance",
    "name_similarity",
    "doc_similarity",
    "class_name_from_qualname",
    "method_first_param_mismatch",
]
