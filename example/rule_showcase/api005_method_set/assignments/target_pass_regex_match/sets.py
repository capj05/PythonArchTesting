"""Target: target_pass_regex_match — HandlerSet adds a 4th handle_* method.

Total of 4 ``handle_*`` methods is still within ``min_count=2`` / ``max_count=5``.
"""


class HandlerSet:
    def handle_create(self) -> None:
        return None

    def handle_update(self) -> None:
        return None

    def handle_delete(self) -> None:
        return None

    def handle_archive(self) -> None:
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
