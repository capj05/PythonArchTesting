"""Same layering, different result: the service rounds and the controller
reports the total in cents. Logic is not what the rules check, so it passes.
"""

from __future__ import annotations

from typing import Any


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    total = service.place(request["id"], request["prices"])
    return {"status": "accepted", "total_cents": int(total * 100)}
