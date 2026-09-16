"""Target: target_fail_declared_only — DeclaredHandlers inherits process_* methods.

The process_a / process_b methods live on a base class; ``declared_only=True``
should reject this because they are not declared on ``DeclaredHandlers`` itself.
"""


class HandlerSet:
    def handle_create(self) -> None:
        return None

    def handle_update(self) -> None:
        return None

    def handle_delete(self) -> None:
        return None


class AliasMethods:
    def validate(self) -> bool:
        return True


class ClassmethodFactories:
    @classmethod
    def create(cls) -> "ClassmethodFactories":
        return cls()


class _ProcessBase:
    def process_a(self) -> None:
        return None

    def process_b(self) -> None:
        return None


class DeclaredHandlers(_ProcessBase):
    pass
