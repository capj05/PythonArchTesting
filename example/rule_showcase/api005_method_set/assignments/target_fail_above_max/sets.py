"""Target: target_fail_above_max — HandlerSet has 6 handle_* methods (over max=5)."""


class HandlerSet:
    def handle_create(self) -> None:
        return None

    def handle_update(self) -> None:
        return None

    def handle_delete(self) -> None:
        return None

    def handle_archive(self) -> None:
        return None

    def handle_restore(self) -> None:
        return None

    def handle_purge(self) -> None:
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
