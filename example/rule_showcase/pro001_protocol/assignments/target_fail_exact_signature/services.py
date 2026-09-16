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
    # Extra defaulted parameter — under signature_mode="exact" the
    # signature must match the protocol byte-for-byte, so this fails.
    def read(self, path: str, encoding: str = "utf-8") -> str:
        return ""
