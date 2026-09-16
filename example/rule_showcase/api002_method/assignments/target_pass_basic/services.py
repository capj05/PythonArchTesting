"""target_pass_basic -- every required method present, declared on the class,
with matching signatures and matching method kinds.
"""


class Service:
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

    def internal_check(self) -> None:
        return None

    def optional_hook(self) -> None:
        return None
