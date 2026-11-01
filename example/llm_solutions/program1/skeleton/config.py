"""Application settings, shared through one instance."""

from __future__ import annotations


class AppConfig:
    _instance: AppConfig | None = None

    def __init__(self) -> None:
        raise NotImplementedError

    @classmethod
    def instance(cls) -> AppConfig:
        raise NotImplementedError
