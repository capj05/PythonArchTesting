"""Mock module B with circular import."""

from .circular_module_a import function_a


def function_b():
    """Function B that calls function A."""
    return function_a()


class ClassB:
    """Class B in circular module."""

    def method_b(self):
        """Method B."""
        return "result_b"
