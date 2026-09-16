"""target_fail_declared_only -- ``internal_check`` is inherited from a
base class instead of being declared on ``Service`` itself. Because the
reference rule on ``internal_check`` uses ``declared_only=True``,
inheritance is NOT acceptable and this must FAIL.
"""


class _BaseService:
    def internal_check(self) -> None:
        return None


class Service(_BaseService):
    def process(self, payload: dict) -> bool:
        return bool(payload)

    def validate(self, value: str) -> bool:
        return bool(value)

    def compute(self, x: int, y: int) -> int:
        return x + y

    def count_items(self) -> int:
        return 0

    def helper(self) -> None:
        return None

    # `internal_check` is inherited from _BaseService -- declared_only=True
    # rule should reject this.

    def optional_hook(self) -> None:
        return None
