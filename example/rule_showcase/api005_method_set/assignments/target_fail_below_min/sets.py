"""Target: target_fail_below_min — HandlerSet has only 1 handle_* method (below min=2)."""


class HandlerSet:
    def handle_create(self) -> None:
        return None


class AliasMethods:
    def validate(self) -> bool:
        return True


class ClassmethodFactories:
    @classmethod
    def create(cls) -> "ClassmethodFactories":
        return cls()


class DeclaredHandlers:
    def process_a(self) -> None:
        return None

    def process_b(self) -> None:
        return None
