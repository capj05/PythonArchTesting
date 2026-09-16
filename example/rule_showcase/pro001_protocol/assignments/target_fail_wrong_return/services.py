class FileStorage:
    def save(self, key: str, value: bytes) -> None:
        pass

    def load(self, key: str) -> bytes:
        return b""


class TickCounter:
    # Return annotation is `str` instead of `int` —
    # `return_annotation="error"` escalates the mismatch to a hard fail.
    def increment(self) -> str:
        return "1"


class WidgetBuilder:
    @classmethod
    def create(cls) -> "WidgetBuilder":
        return cls()


class TextReader:
    def read(self, path: str) -> str:
        return ""
