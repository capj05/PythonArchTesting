"""Application settings, shared through one instance."""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import is_runtime_singleton


class AppConfig:
    __archtest__: Annotated[
        None, is_runtime_singleton(access="instance", cases=[{"args": []}])
    ]

    _instance: AppConfig | None = None

    def __init__(self) -> None:
        self.currency = "CZK"

    @classmethod
    def instance(cls) -> AppConfig:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
