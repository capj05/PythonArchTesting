"""Target: focuses on ``ConstructorOnly``; all six classes verbatim. Expected verdict: PASS."""


class ClassmethodFactory:
    def __init__(self, value: int) -> None:
        self.value = value

    @classmethod
    def create(cls, value: int) -> "ClassmethodFactory":
        return cls(value)


class StaticmethodFactory:
    def __init__(self, value: int) -> None:
        self.value = value

    @staticmethod
    def build(value: int) -> "StaticmethodFactory":
        return StaticmethodFactory(value)


class ConstructorOnly:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class ExtendedMatch:
    def __init__(self, raw: str) -> None:
        self.raw = raw

    @classmethod
    def make(cls, raw: str) -> "ExtendedMatch":
        return cls(raw)


class StaticAttributeFactory:
    def __init__(self, n: int) -> None:
        self.n = n

    def _make_impl(cls, n: int) -> "StaticAttributeFactory":
        return cls(n)

    make = classmethod(_make_impl)


class CheckedReturnAnnotation:
    def __init__(self, value: int) -> None:
        self.value = value

    @classmethod
    def create(cls, value: int) -> "CheckedReturnAnnotation":
        return cls(value)
