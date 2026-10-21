"""Defaults come from a mixin's class attributes, overrides from a loop."""

from __future__ import annotations

from typing import Any


class _Defaults:
    host = "localhost"
    port = 5432
    debug = False


class Settings(_Defaults):
    def __init__(self, overrides: dict[str, Any]) -> None:
        for key, value in overrides.items():
            if key in ("host", "port", "debug"):
                setattr(self, key, value)
