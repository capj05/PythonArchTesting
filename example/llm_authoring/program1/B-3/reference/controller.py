"""Presentation layer: checks the request and delegates to the service."""

from __future__ import annotations

from typing import Annotated, Any

from pythonarchtesting.rules import forbid_imports

__archtest__: Annotated[
    None,
    forbid_imports("repository", "models", scope="module", mode="direct"),
]


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    if not request.get("prices"):
        return {"status": "error", "reason": "empty order"}
    total = service.place(request["id"], request["prices"])
    return {"status": "ok", "total": total}
