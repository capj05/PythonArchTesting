"""Controller: talks to the service only."""

from __future__ import annotations

from typing import Any


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    total = service.place(request["id"], request["prices"])
    return {"status": "ok", "total": total}
