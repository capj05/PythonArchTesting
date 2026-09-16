"""Reference services that declare protocol-conformance markers."""

from typing import Annotated

from pythonarchtesting.rules import implements_protocol

from .protocols import Builder, Counter, Storage, StrictReader


class FileStorage:
    __archtest__: Annotated[
        None, implements_protocol(Storage, signature_mode="compatible")
    ]

    def save(self, key: str, value: bytes) -> None:
        pass

    def load(self, key: str) -> bytes:
        return b""


class TickCounter:
    __archtest__: Annotated[
        None, implements_protocol(Counter, return_annotation="error")
    ]

    def increment(self) -> int:
        return 1


class WidgetBuilder:
    __archtest__: Annotated[
        None, implements_protocol(Builder, enforce_method_kind=True)
    ]

    @classmethod
    def create(cls) -> "WidgetBuilder":
        return cls()


class TextReader:
    __archtest__: Annotated[
        None, implements_protocol(StrictReader, signature_mode="exact")
    ]

    def read(self, path: str) -> str:
        return ""
