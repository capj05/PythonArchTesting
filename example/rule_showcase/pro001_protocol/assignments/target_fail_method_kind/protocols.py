from typing import Protocol


class Storage(Protocol):
    def save(self, key: str, value: bytes) -> None: ...
    def load(self, key: str) -> bytes: ...


class Counter(Protocol):
    def increment(self) -> int: ...


class Builder(Protocol):
    @classmethod
    def create(cls) -> "Builder": ...


class StrictReader(Protocol):
    def read(self, path: str) -> str: ...
