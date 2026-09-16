"""target_pass_inherited -- ``helper`` is inherited from ``_BaseService``
rather than declared on ``Service`` directly. Because the reference rule
on ``helper`` uses ``declared_only=False`` (default), inheritance is
acceptable and this must PASS.
"""


class _BaseService:
    def helper(self) -> None:
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

    # `helper` is inherited from _BaseService -- not redeclared here.

    def internal_check(self) -> None:
        return None

    def optional_hook(self) -> None:
        return None
