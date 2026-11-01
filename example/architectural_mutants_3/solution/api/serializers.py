"""Requests and responses as plain dictionaries."""

from __future__ import annotations

from typing import Any


class RequestError(Exception):
    pass


def require(request: dict[str, Any], *names: str) -> list[Any]:
    missing = [name for name in names if request.get(name) in (None, "")]
    if missing:
        raise RequestError(f"missing {', '.join(missing)}")
    return [request[name] for name in names]


def as_int(value: Any, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RequestError(f"{name} must be a whole number") from exc


def ok(**fields: Any) -> dict[str, Any]:
    return {"status": "ok", **fields}


def error(reason: str) -> dict[str, Any]:
    return {"status": "error", "reason": reason}
