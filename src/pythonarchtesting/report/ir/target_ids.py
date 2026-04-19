"""Stable target-id normalization helpers for run reports."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Dict, List, Tuple

_SLUG_RE = re.compile(r"[^a-z0-9._-]+")


def slugify_target_id(value: str) -> str:
    """Build a slug-safe target id."""
    slug = _SLUG_RE.sub("-", (value or "").strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "target"


def path_hash8(path_value: str) -> str:
    """Return stable 8-char hash for path-based collision suffixes."""
    return hashlib.sha1(path_value.encode("utf-8")).hexdigest()[:8]


def normalize_target_ids(
    target_payloads: List[dict],
) -> Dict[Tuple[str, str], Tuple[str, str]]:
    """
    Build stable, slug-safe target ids.

    Returns mapping:
    (original_target_id, target_path) -> (slug_target_id, display_name).
    """
    entries: List[Tuple[str, str, str]] = []
    for payload in target_payloads:
        display = str(payload.get("target_id") or "")
        target_path = str(payload.get("target_path") or "")
        entries.append((display, target_path, slugify_target_id(display)))

    by_slug: Dict[str, List[Tuple[str, str, str]]] = {}
    for display, target_path, slug in entries:
        by_slug.setdefault(slug, []).append((display, target_path, slug))

    out: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for slug, rows in by_slug.items():
        if len(rows) == 1:
            display, target_path, _ = rows[0]
            out[(display, target_path)] = (slug, display)
            continue

        used_ids: Dict[str, int] = {}
        ordered_rows = sorted(
            rows, key=lambda r: (str(Path(r[1])) if r[1] else "", r[0])
        )
        for display, target_path, _ in ordered_rows:
            norm_path = str(Path(target_path)) if target_path else ""
            candidate = f"{slug}--{path_hash8(norm_path)}"
            used_ids[candidate] = used_ids.get(candidate, 0) + 1
            if used_ids[candidate] > 1:
                candidate = f"{candidate}--{used_ids[candidate]}"
            out[(display, target_path)] = (candidate, display)
    return out
