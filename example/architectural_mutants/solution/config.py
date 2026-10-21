"""Application settings, shared through one instance."""

from __future__ import annotations


class AppConfig:
    _instance: AppConfig | None = None

    def __init__(self) -> None:
        self.currency = "CZK"

    @classmethod
    def instance(cls) -> AppConfig:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
