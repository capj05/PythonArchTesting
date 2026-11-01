"""Driving adapter: request handlers that talk to the application only."""

from __future__ import annotations
from typing import Any


def lend_book(request: dict[str, Any], service: Any) -> dict[str, Any]:
    raise NotImplementedError


def return_book(request: dict[str, Any], service: Any) -> dict[str, Any]:
    raise NotImplementedError
