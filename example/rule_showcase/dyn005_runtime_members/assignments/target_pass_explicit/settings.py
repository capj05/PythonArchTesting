"""Plain assignments: the same members, written out."""

from __future__ import annotations

from typing import Any


class Settings:
    def __init__(self, overrides: dict[str, Any]) -> None:
        self.host = overrides.get("host", "localhost")
        self.port = overrides.get("port", 5432)
        self.debug = overrides.get("debug", False)
