"""
Performance tests for type utilities.
"""

import time
from typing import Dict, List, Optional

from pythonarchtesting.util.type_utils import get_origin_type, get_type_args


def test_type_utils_performance():
    complex_type = List[Dict[str, Optional[int]]]
    iterations = 1000

    start_time = time.time()
    for _ in range(iterations):
        get_origin_type(complex_type)
    origin_time = time.time() - start_time

    start_time = time.time()
    for _ in range(iterations):
        get_type_args(complex_type)
    args_time = time.time() - start_time

    assert origin_time < 1.0, f"get_origin_type too slow: {origin_time}s"
    assert args_time < 1.0, f"get_type_args too slow: {args_time}s"
