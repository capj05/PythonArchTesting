"""
Tests for type utility functions.

This module contains unit tests for type-related utilities.
"""

from typing import List

from src.util.type_utils import (
    get_origin_type,
    get_type_args,
    get_type_name,
    is_optional_type,
    is_union_type,
)


class TestTypeUtils:
    """Test cases for type utility functions."""

    def test_get_origin_type_basic(self):
        """Test getting origin type for basic types."""
        assert get_origin_type(int) is int
        assert get_origin_type(str) is str
        assert get_origin_type(list) is list
        assert get_origin_type(dict) is dict

    def test_get_origin_type_generic(self):
        """Test getting origin type for generic types."""
        from typing import Dict, List, Set

        assert get_origin_type(List[int]) is list
        assert get_origin_type(Dict[str, int]) is dict
        assert get_origin_type(Set[str]) is set

    def test_get_type_args_basic(self):
        """Test getting type arguments for basic types."""
        from typing import Dict, List, Tuple

        assert get_type_args(int) == ()
        assert get_type_args(str) == ()
        assert get_type_args(List[int]) == (int,)
        assert get_type_args(Dict[str, int]) == (str, int)
        assert get_type_args(Tuple[int, str, float]) == (int, str, float)

    def test_is_optional_type_detection(self):
        """Test optional type detection."""
        from typing import Optional, Union

        assert is_optional_type(Optional[int])
        assert is_optional_type(Optional[str])
        assert is_optional_type(Union[int, None])
        assert is_optional_type(Union[str, None])

        assert is_optional_type(int) is False
        assert is_optional_type(str) is False
        assert is_optional_type(Union[int, str]) is False
        assert is_optional_type(List[int]) is False

    def test_is_union_type_detection(self):
        """Test union type detection."""
        from typing import Optional, Union

        assert is_union_type(Union[int, str])
        assert is_union_type(Union[int, str, float])
        assert is_union_type(Optional[int])  # Optional is Union with None

        assert is_union_type(int) is False
        assert is_union_type(str) is False
        assert is_union_type(List[int]) is False

    def test_get_type_name_basic(self):
        """Test getting type names for basic types."""
        assert get_type_name(int) == "int"
        assert get_type_name(str) == "str"
        assert get_type_name(list) == "list"
        assert get_type_name(dict) == "dict"

    def test_get_type_name_generic(self):
        """Test getting type names for generic types."""
        from typing import Dict, List, Optional

        assert "List" in get_type_name(List[int])
        assert "Dict" in get_type_name(Dict[str, int])
        assert "Optional" in get_type_name(Optional[str])

        # Test Python 3.10+ union syntax
        try:
            union_type = str | None
            type_name = get_type_name(union_type)
            # In Python 3.10+, str | None creates a types.UnionType
            # The representation should be either "Optional[str]" or
            # "Union[str, None]"
            assert "Optional" in type_name or "Union" in type_name or "|" in type_name
        except (SyntaxError, TypeError):
            # Python version doesn't support | syntax
            pass

    def test_nested_type_analysis(self):
        """Test analysis of nested types."""
        from typing import Dict, List, Optional

        complex_type = List[Dict[str, Optional[int]]]

        origin = get_origin_type(complex_type)
        args = get_type_args(complex_type)

        assert origin is list
        assert len(args) == 1

        # Analyze the first argument
        first_arg = args[0]
        assert get_origin_type(first_arg) is dict
        assert get_type_args(first_arg) == (str, Optional[int])

    def test_type_utils_with_none(self):
        """Test type utilities with None type."""
        assert get_origin_type(None) is None or get_origin_type(type(None)) is type(
            None
        )
        assert get_type_args(None) == ()
        assert is_optional_type(None) is False
        assert is_union_type(None) is False

    def test_type_utils_with_any(self):
        """Test type utilities with Any type."""
        from typing import Any

        assert get_origin_type(Any) is Any
        assert get_type_args(Any) == ()
        assert is_optional_type(Any) is False
        assert is_union_type(Any) is False

    def test_type_utils_with_callable(self):
        """Test type utilities with Callable types."""
        from typing import Callable

        simple_callable = Callable[[int, str], bool]
        assert get_origin_type(simple_callable) is not None
        assert len(get_type_args(simple_callable)) >= 2

    def test_type_utils_edge_cases(self):
        """Test type utilities with edge cases."""
        from typing import Generic, TypeVar

        T = TypeVar("T")

        # TypeVar handling
        assert get_origin_type(T) is T or get_origin_type(T) is None
        assert get_type_args(T) == ()

        # Generic handling
        class GenericClass(Generic[T]):
            pass

        generic_type = GenericClass[int]
        origin = get_origin_type(generic_type)
        assert origin is GenericClass or origin is not None

    def test_type_utils_consistency(self):
        """Test consistency across different type utilities."""
        from typing import Optional, Union

        # Optional should be detected as both optional and union
        optional_type = Optional[int]
        assert is_optional_type(optional_type)
        assert is_union_type(optional_type)

        # Regular union should only be detected as union
        union_type = Union[int, str]
        assert is_optional_type(union_type) is False
        assert is_union_type(union_type)
