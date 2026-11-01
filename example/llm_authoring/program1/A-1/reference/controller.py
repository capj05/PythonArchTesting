"""Presentation layer: checks the request and delegates to the service."""

from __future__ import annotations

from typing import Any


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    if not request.get("prices"):
        return {"status": "error", "reason": "empty order"}
    total = service.place(request["id"], request["prices"])
    return {"status": "ok", "total": total}
