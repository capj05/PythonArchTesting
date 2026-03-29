"""Mock module A with circular import."""

from .circular_module_b import function_b


def function_a():
    """Function A that calls function B."""
    return function_b()


class ClassA:
    """Class A in circular module."""

    def method_a(self):
        """Method A."""
        return "result_a"
