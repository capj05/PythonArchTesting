"""
Data Processor Module - Target 4 Implementation
Different approach with additional features and alternative method names.
"""

import math
from typing import Any, Dict, List, Optional, Union

NumericData = Union[int, float]


class DataProcessor:
    """Enhanced data processor with additional functionality."""

    def __init__(self):
        """Initialize data processor."""
        self._data_points: List[NumericData] = []
        self._labels: Dict[int, str] = {}
        self._data_added_count = 0

    def insert_value(self, value: NumericData, label: Optional[str] = None) -> None:
        """Insert a single value (different method name)."""
        if not isinstance(value, (int, float)):
            raise TypeError("Value must be numeric")
        self._data_points.append(value)
        if label:
            self._labels[self._data_added_count] = label
        self._data_added_count += 1

    def insert_batch(self, values: List[NumericData]) -> None:
        """Insert multiple values (different method name)."""
        for i, value in enumerate(values):
            if not isinstance(value, (int, float)):
                raise TypeError(f"Value at index {i} is not numeric")
            self._data_points.append(value)
            self._data_added_count += 1

    def calculate_average(self) -> float:
        """Calculate average (different method name)."""
        if not self._data_points:
            raise ValueError("No data points available")
        return sum(self._data_points) / len(self._data_points)

    def calculate_median_value(self) -> float:
        """Calculate median (different method name)."""
        if not self._data_points:
            raise ValueError("No data points available")
        sorted_data = sorted(self._data_points)
        n = len(sorted_data)
        if n % 2 == 0:
            return (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2
        else:
            return sorted_data[n // 2]

    def calculate_standard_deviation(self) -> float:
        """Calculate standard deviation (different method name)."""
        if not self._data_points:
            raise ValueError("No data points available")
        if len(self._data_points) <= 1:
            return 0.0

        mean = self.calculate_average()
        variance = sum((x - mean) ** 2 for x in self._data_points) / (
            len(self._data_points) - 1
        )
        return math.sqrt(variance)

    def get_range_values(self) -> tuple[NumericData, NumericData]:
        """Get range values (different method name)."""
        if not self._data_points:
            raise ValueError("No data points available")
        return (min(self._data_points), max(self._data_points))

    def filter_data_by_range(
        self, min_val: NumericData, max_val: NumericData
    ) -> List[NumericData]:
        """Filter data by range (different method name)."""
        return [x for x in self._data_points if min_val <= x <= max_val]

    def generate_statistics_report(self) -> Dict[str, Any]:
        """Generate statistics report (different method name)."""
        if not self._data_points:
            return {"status": "error", "message": "No data available"}

        return {
            "status": "success",
            "data_points_count": len(self._data_points),
            "average": self.calculate_average(),
            "median": self.calculate_median_value(),
            "standard_deviation": self.calculate_standard_deviation(),
            "range": self.get_range_values(),
            "labels": self._labels.copy(),
            "total_inserted": self._data_added_count,
        }

    def reset_all_data(self) -> None:
        """Reset all data (different method name)."""
        self._data_points.clear()
        self._labels.clear()
        self._data_added_count = 0

    def get_data_count(self) -> int:
        """Get data count (extra method)."""
        return len(self._data_points)

    def has_data(self) -> bool:
        """Check if has data (extra method)."""
        return len(self._data_points) > 0
