"""Target: target_fail_wrong_method_kind — ClassmethodFactories.create is a regular instance method.

The marker requires ``method_kind="class"``; an instance method should fail.
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
    def create(self) -> "ClassmethodFactories":
        return self


class DeclaredHandlers:
    def process_a(self) -> None:
        return None

    def process_b(self) -> None:
        return None
