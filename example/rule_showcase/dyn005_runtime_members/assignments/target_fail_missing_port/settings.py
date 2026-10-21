"""Only the keys that were passed in end up on the object.

With no overrides the instance has no ``port`` (nor ``host``/``debug``).
"""

from __future__ import annotations

from typing import Any


class Settings:
    def __init__(self, overrides: dict[str, Any]) -> None:
        for key, value in overrides.items():
            if key != "password":
                setattr(self, key, value)
