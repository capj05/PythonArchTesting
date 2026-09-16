class FileStorage:
    def save(self, key: str, value: bytes) -> None:
        pass

    def load(self, key: str) -> bytes:
        return b""


class TickCounter:
    def increment(self) -> int:
        return 1


class WidgetBuilder:
    # `create` is a regular instance method instead of a classmethod —
    # `enforce_method_kind=True` rejects the kind mismatch.
    def create(self) -> "WidgetBuilder":
        return WidgetBuilder()


class TextReader:
    def read(self, path: str) -> str:
        return ""
