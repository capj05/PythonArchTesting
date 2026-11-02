"""Driving adapter: request handlers that talk to the application only."""

from __future__ import annotations

from typing import Any


def lend_book(request: dict[str, Any], service: Any) -> dict[str, Any]:
    if not request.get("book") or not request.get("member"):
        return {"status": "error", "reason": "book and member are required"}
    due = service.lend(request["book"], request["member"])
    return {"status": "ok", "due": due}


def return_book(request: dict[str, Any], service: Any) -> dict[str, Any]:
    returned = service.give_back(request["book"])
    return {"status": "ok" if returned else "not_lent"}
