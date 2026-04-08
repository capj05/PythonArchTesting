"""
Fixtures specific to performance tests.
"""

import time
from typing import Any, Dict, List

import psutil
import pytest

from pythonarchtesting.state import ProjectState


@pytest.fixture
def performance_test_data() -> Dict[str, Any]:
    """Provide data for performance testing."""
    return {
        "small_dataset": list(range(100)),
        "medium_dataset": list(range(1000)),
        "large_dataset": list(range(10000)),
        "complex_structure": {
            f"key_{i}": {
                "nested": list(range(10)),
                "data": f"value_{i}",
                "metadata": {
                    "created": time.time(),
                    "tags": [f"tag_{j}" for j in range(5)],
                },
            }
            for i in range(100)
        },
    }


@pytest.fixture
def performance_monitor():
    """Provide performance monitoring capabilities."""

    class PerformanceMonitor:
        def __init__(self):
            self.process = psutil.Process()
            self.start_time = None
            self.start_memory = None
            self.peak_memory = None

        def start(self):
            """Start monitoring."""
            self.start_time = time.time()
            self.start_memory = self.process.memory_info().rss
            self.peak_memory = self.start_memory

        def stop(self) -> Dict[str, float]:
            """Stop monitoring and return metrics."""
            end_time = time.time()
            end_memory = self.process.memory_info().rss

            return {
                "duration": end_time - self.start_time,
                "memory_used": end_memory - self.start_memory,
                "peak_memory": self.peak_memory - self.start_memory,
            }

        def update_peak(self):
            """Update peak memory usage."""
            current_memory = self.process.memory_info().rss
            if current_memory > self.peak_memory:
                self.peak_memory = current_memory

    return PerformanceMonitor()


@pytest.fixture
def benchmark_data() -> List[Dict[str, Any]]:
    """Generate data for benchmarking."""
    return [
        {
            "id": i,
            "name": f"item_{i}",
            "value": i * 2,
            "metadata": {
                "created": time.time(),
                "tags": [f"tag_{j}" for j in range(i % 5)],
            },
        }
        for i in range(1000)
    ]


@pytest.fixture
def clean_project_state() -> ProjectState:
    """Provide a clean project state instance."""
    state = ProjectState("/test", [])
    state.reset()
    return state
