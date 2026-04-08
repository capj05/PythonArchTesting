"""
Type checking utilities.

This module provides utilities for validating types at runtime,
with support for generic types like List[T], Dict[K, V], etc.
"""

from types import UnionType
from typing import Any, Callable, Union, get_args, get_origin


def _check_list_type(value: list, expected_type: Any) -> bool:
    """
    Check if a list value matches a List[T] type.

    Args:
        value: The list to check
        expected_type: The expected List[T] type

    Returns:
        True if the list matches the expected type, False otherwise
    """
    # Get the type arguments (e.g., int from List[int])
    args = get_args(expected_type)
    if not args:
        return True  # List with no type args, just check it's a list

    # Check each item in the list
    item_type = args[0]

    # If item type is Any, all items are valid
    if item_type is Any:
        return True

    # Empty lists are valid for any item type
    if not value:
        return True

    return all(is_instance_of_generic(item, item_type) for item in value)


def _check_key_types(key_type: Any, keys: list) -> bool:
    """
    Check if all keys in a dictionary match the expected type.

    Args:
        key_type: The expected key type
        keys: List of keys to check

    Returns:
        True if all keys match the expected type, False otherwise
    """
    if key_type is Any:
        return True
    return all(is_instance_of_generic(k, key_type) for k in keys)


def _check_value_types(value_type: Any, values: list) -> bool:
    """
    Check if all values in a dictionary match the expected type.

    Args:
        value_type: The expected value type
        values: List of values to check

    Returns:
        True if all values match the expected type, False otherwise
    """
    if value_type is Any:
        return True
    return all(is_instance_of_generic(v, value_type) for v in values)


def _check_dict_type(value: dict, expected_type: Any) -> bool:
    """
    Check if a dict value matches a Dict[K, V] type.

    Args:
        value: The dictionary to check
        expected_type: The expected Dict[K, V] type

    Returns:
        True if the dictionary matches the expected type, False otherwise
    """
    # Get the type arguments (e.g., str, int from Dict[str, int])
    args = get_args(expected_type)
    if not args or len(args) != 2:
        return True  # Dict with no type args, just check it's a dict

    # If empty dict, it's valid for any key/value types
    if not value:
        return True

    # Extract key and value types
    key_type, value_type = args

    # If both key and value types are Any, all entries are valid
    if key_type is Any and value_type is Any:
        return True

    # Check keys and values separately
    keys_valid = _check_key_types(key_type, list(value.keys()))
    values_valid = _check_value_types(value_type, list(value.values()))

    return keys_valid and values_valid


def _check_set_type(value: set, expected_type: Any) -> bool:
    """
    Check if a set value matches a Set[T] type.

    Args:
        value: The set to check
        expected_type: The expected Set[T] type

    Returns:
        True if the set matches the expected type, False otherwise
    """
    # Get the type arguments (e.g., int from Set[int])
    args = get_args(expected_type)
    if not args:
        return True  # Set with no type args, just check it's a set

    # If empty set, it's valid for any item type
    if not value:
        return True

    # If item type is Any, all items are valid
    item_type = args[0]
    if item_type is Any:
        return True

    # Check each item in the set
    return all(is_instance_of_generic(item, item_type) for item in value)


def _check_container_type(value: Any, expected_type: Any) -> bool:
    """
    Check if a container (list, dict, set) matches the expected generic type.

    Args:
        value: The container to check
        expected_type: The expected generic type

    Returns:
        True if the container matches the expected type, False otherwise
    """
    origin = get_origin(expected_type)

    if origin is list:
        if not isinstance(value, list):
            return False
        return _check_list_type(value, expected_type)

    if origin is dict:
        if not isinstance(value, dict):
            return False
        return _check_dict_type(value, expected_type)

    if origin is set:
        if not isinstance(value, set):
            return False
        return _check_set_type(value, expected_type)

    # For other generic types, just check the origin type
    if origin is not None:
        try:
            return isinstance(value, origin)
        except TypeError:
            # Some types can't be used with isinstance
            return True
    return False


def is_instance_of_generic(value: Any, expected_type: Any) -> bool:
    """
    Check if a value is an instance of a generic type like List[int], Dict[str, int], etc.

    This function handles both standard types and generic types from the typing module.
    It recursively checks elements inside containers like lists, dicts, and sets.

    Args:
        value: The value to check
        expected_type: The expected type (may be a generic type)

    Returns:
        True if the value is an instance of the expected type, False otherwise
    """
    # Special case for Any - it matches anything
    if expected_type is Any:
        return True

    # Handle non-generic types directly
    origin = get_origin(expected_type)
    if origin is None:
        try:
            return isinstance(value, expected_type)
        except TypeError:
            # Some types like typing.ClassVar can't be used with isinstance
            return True

    # Handle generic container types
    return _check_container_type(value, expected_type)


def get_origin_type(tp: Any) -> Any:
    """Return the origin type for generics, or the type itself."""
    origin = get_origin(tp)
    if origin is None:
        return tp
    if origin is Union or origin is UnionType:
        return Union
    return origin


def get_type_args(tp: Any) -> tuple:
    """Return type arguments for a generic type."""
    return get_args(tp)


def is_optional_type(tp: Any) -> bool:
    """Return True if type is Optional[T] (Union[T, None])."""
    origin = get_origin_type(tp)
    if origin is not Union:
        return False
    args = get_type_args(tp)
    return len(args) == 2 and type(None) in args


def is_union_type(tp: Any) -> bool:
    """Return True if the type is a Union."""
    return get_origin_type(tp) is Union


def _type_display_name(tp: Any) -> str:
    if tp is type(None):
        return "None"
    if hasattr(tp, "__name__"):
        return str(tp.__name__)
    return str(tp)


def get_type_name(tp: Any) -> str:
    """Return a readable name for a type or typing construct."""
    if is_optional_type(tp):
        args = [a for a in get_type_args(tp) if a is not type(None)]
        inner = _type_display_name(args[0]) if args else "Any"
        return f"Optional[{inner}]"

    origin = get_origin(tp)
    if origin is not None:
        if origin is Union or origin is UnionType:
            union_args = list(get_type_args(tp))
            if union_args:
                arg_names = ", ".join(_type_display_name(a) for a in union_args)
                return f"Union[{arg_names}]"
            return "Union"
        origin_args = list(get_type_args(tp))
        origin_map = {
            list: "List",
            dict: "Dict",
            set: "Set",
            tuple: "Tuple",
        }
        name = origin_map.get(origin, _type_display_name(origin))
        if origin_args:
            arg_names = ", ".join(_type_display_name(a) for a in origin_args)
            return f"{name}[{arg_names}]"
        return name

    if is_union_type(tp):
        union_args = list(get_type_args(tp))
        if union_args:
            arg_names = ", ".join(_type_display_name(a) for a in union_args)
            return f"Union[{arg_names}]"
        return "Union"

    return _type_display_name(tp)


def check_function_types(
    func: Callable,
    strict: bool = False,
    check_args: bool = True,
    check_return: bool = True,
) -> list[str]:
    """
    Check function parameter and return types against annotations.

    Args:
        func: The function to check
        strict: If True, raise exceptions instead of returning violations
        check_args: Whether to check argument types
        check_return: Whether to check return type

    Returns:
        List of violation messages (empty if no violations)

    Raises:
        TypeError: If strict=True and type violations are found
    """
    import inspect

    violations: list[str] = []

    if not hasattr(func, "__annotations__") or not func.__annotations__:
        return violations

    annotations = func.__annotations__
    sig = inspect.signature(func)

    # Check parameter types
    if check_args:
        for param_name, param in sig.parameters.items():
            if param_name in annotations and param_name != "return":
                expected_type = annotations[param_name]
                # Note: This is a simplified check - in a real implementation,
                # we'd need to call the function and check actual argument types
                # For now, we just validate that the annotation is a valid type
                try:
                    get_origin(expected_type)
                    get_args(expected_type)
                except Exception as e:
                    violations.append(
                        f"Invalid type annotation for parameter '{param_name}': {e}"
                    )

    # Check return type
    if check_return and "return" in annotations:
        return_type = annotations["return"]
        try:
            get_origin(return_type)
            get_args(return_type)
        except Exception as e:
            violations.append(f"Invalid return type annotation: {e}")

    if strict and violations:
        raise TypeError("; ".join(violations))

    return violations


__all__ = [
    "get_origin_type",
    "get_type_args",
    "is_optional_type",
    "is_union_type",
    "get_type_name",
    "is_instance_of_generic",
    "check_function_types",
]
