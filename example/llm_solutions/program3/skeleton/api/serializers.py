"""Requests and responses as plain dictionaries."""

from __future__ import annotations
from typing import Any


class RequestError(Exception):
    pass


def require(request: dict[str, Any], *names: str) -> list[Any]:
    raise NotImplementedError


def as_int(value: Any, name: str) -> int:
    raise NotImplementedError


def ok(**fields: Any) -> dict[str, Any]:
    raise NotImplementedError


def error(reason: str) -> dict[str, Any]:
    raise NotImplementedError
