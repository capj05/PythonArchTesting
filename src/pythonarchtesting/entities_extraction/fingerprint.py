from __future__ import annotations

import ast
import hashlib
import io
import json
import tokenize
from collections import Counter
from typing import Sequence

from pythonarchtesting.entities import hash_text


def _normalize_source_segment(segment: str) -> str:
    if not segment:
        return ""
    lines = [line.rstrip() for line in segment.splitlines()]
    while lines and lines[-1] == "":
        lines.pop()
    cleaned = "\n".join(lines)

    tokens = tokenize.generate_tokens(io.StringIO(cleaned).readline)
    filtered: list[tokenize.TokenInfo] = [
        tok for tok in tokens if tok.type != tokenize.COMMENT
    ]
    rebuilt = tokenize.untokenize(filtered)
    rebuilt_lines = [line.rstrip() for line in str(rebuilt).splitlines()]
    while rebuilt_lines and rebuilt_lines[-1] == "":
        rebuilt_lines.pop()
    return "\n".join(rebuilt_lines)


def source_hash_from_segment(segment: str) -> str:
    normalized = _normalize_source_segment(segment)
    return hash_text(normalized)


def _tokenize_ast(node: ast.AST, bag: Counter) -> None:
    token = type(node).__name__
    bag[token] += 1

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            bag["Call:Attribute"] += 1
        else:
            bag["Call:Name"] += 1
    elif isinstance(node, ast.BinOp):
        bag[f"BinOp:{type(node.op).__name__}"] += 1
    elif isinstance(node, ast.Compare):
        for op in node.ops:
            bag[f"Compare:{type(op).__name__}"] += 1
    elif isinstance(node, ast.Constant):
        bag[f"Constant:{type(node.value).__name__}"] += 1

    # Stop at nested definitions to keep fingerprints stable.
    if isinstance(
        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
    ):
        return

    for child in ast.iter_child_nodes(node):
        _tokenize_ast(child, bag)


def ast_fingerprint_from_body(body: Sequence[ast.stmt]) -> tuple[str, Counter]:
    bag: Counter = Counter()
    for stmt in body:
        _tokenize_ast(stmt, bag)
    payload = sorted(bag.items())
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return fingerprint, bag


__all__ = ["source_hash_from_segment", "ast_fingerprint_from_body"]
