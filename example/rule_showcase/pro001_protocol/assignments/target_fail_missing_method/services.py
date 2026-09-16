class FileStorage:
    # `load` removed — Storage protocol no longer satisfied.
    def save(self, key: str, value: bytes) -> None:
        pass


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
