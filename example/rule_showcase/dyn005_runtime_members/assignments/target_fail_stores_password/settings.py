"""Copies everything it is given, the password included."""

from __future__ import annotations

from typing import Any

DEFAULTS: dict[str, Any] = {"host": "localhost", "port": 5432, "debug": False}


class Settings:
    def __init__(self, overrides: dict[str, Any]) -> None:
        self.__dict__.update({**DEFAULTS, **overrides})
