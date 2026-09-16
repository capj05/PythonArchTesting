"""target_fail_method_kind_mismatch -- ``count_items`` is implemented as a
classmethod instead of a regular instance method. Because the reference
rule has ``enforce_method_kind=True``, this must FAIL.
"""


class Service:
    def process(self, payload: dict) -> bool:
        return bool(payload)

    def validate(self, value: str) -> bool:
        return bool(value)

    def compute(self, x: int, y: int) -> int:
        return x + y

    @classmethod
    def count_items(cls) -> int:
        # method kind drift: classmethod instead of regular method.
        return 0

    def helper(self) -> None:
        return None

    def internal_check(self) -> None:
        return None

    def optional_hook(self) -> None:
        return None
