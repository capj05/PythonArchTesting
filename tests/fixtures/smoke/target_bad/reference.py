def add_numbers(a: int, b: str) -> str:
    return f"{a}{b}"


def filter_even(values: list[int]) -> list[int]:
    result = []
    for value in values:
        if value % 2 == 0:
            result.append(value)
    return result
