from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def canonicalize_payload(value: Any) -> Any:
    """Canonicalize a payload value for consistent hashing."""
    if isinstance(value, dict):
        return {k: canonicalize_payload(value[k]) for k in sorted(value.keys())}
    if isinstance(value, (list, tuple)):
        items = [canonicalize_payload(item) for item in value]

        def _canonical_json(v: Any) -> str:
            return json.dumps(
                v, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            )

        return sorted(items, key=_canonical_json)

    def _safe_json_value(raw: Any) -> Any:
        try:
            json.dumps(raw)
            return raw
        except TypeError:
            return repr(raw)

    return _safe_json_value(value)


def evidence_id(type_: str, payload: Dict[str, Any]) -> str:
    """Generate evidence ID from type and payload."""

    def _canonical_json(value: Any) -> str:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )

    canonical = _canonical_json(
        {"type": type_, "payload": canonicalize_payload(payload)}
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def with_rule_id_suffix(rule_id: str, suffix: str = "") -> str:
    """Append a deterministic declaration suffix to a rule ID when needed."""
    if not suffix:
        return rule_id
    return f"{rule_id}{suffix}"


__all__ = ["canonicalize_payload", "evidence_id", "with_rule_id_suffix"]
