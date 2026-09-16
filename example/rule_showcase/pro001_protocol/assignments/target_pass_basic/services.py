class FileStorage:
    def save(self, key: str, value: bytes) -> None:
        pass

    def load(self, key: str) -> bytes:
        return b""


class TickCounter:
    def increment(self) -> int:
        return 1


class WidgetBuilder:
    @classmethod
    def create(cls) -> "WidgetBuilder":
        return cls()


class TextReader:
    def read(self, path: str) -> str:
        return ""
