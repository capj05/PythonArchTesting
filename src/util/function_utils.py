import inspect
from typing import Callable, Optional, Tuple


def get_func_source_info(
    src_func: Callable,
) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """
    Retrieve source information about a function.

    Args:
        src_func: The function to get source information for

    Returns:
        Tuple containing package name, source file, and source line number
    """
    package = None
    source_file = None
    source_line = None

    # Get package information if available
    if hasattr(src_func, "__module__"):
        package = src_func.__module__

    try:
        # Try to get source info
        source_file = inspect.getsourcefile(src_func)
        source_lines, source_line = inspect.getsourcelines(src_func)
    except (TypeError, OSError):
        # Can't get source info, which is fine
        pass

    return package, source_file, source_line
