"""
Data Processor Module - Target 1 Implementation
Basic implementation with some missing features.
"""

from typing import List, Union

NumericData = Union[int, float]


class DataProcessor:
    """Data processing class for basic operations."""

    def __init__(self):
        self.data = []
        self.metadata = {}

    def add_data_point(self, value: NumericData, label=None):
        """Add a single data point."""
        self.data.append(value)
        if label:
            self.metadata[f"point_{len(self.data)-1}"] = label

    def add_data_batch(self, values: List[NumericData]):
        """Add multiple data points."""
        self.data.extend(values)

    def get_mean(self):
        """Calculate mean."""
        if not self.data:
            return 0
        return sum(self.data) / len(self.data)

    def get_median(self):
        """Calculate median."""
        if not self.data:
            return 0
        sorted_data = sorted(self.data)
        n = len(sorted_data)
        if n % 2 == 0:
            return (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2
        else:
            return sorted_data[n // 2]

    def get_std_dev(self):
        """Calculate standard deviation."""
        if not self.data or len(self.data) <= 1:
            return 0
        mean = self.get_mean()
        variance = sum((x - mean) ** 2 for x in self.data) / (len(self.data) - 1)
        return variance**0.5

    def get_min_max(self):
        """Get min and max values."""
        if not self.data:
            return (0, 0)
        return (min(self.data), max(self.data))

    def filter_by_range(self, min_val: NumericData, max_val: NumericData):
        """Filter data by range."""
        return [x for x in self.data if min_val <= x <= max_val]

    def get_summary(self):
        """Get data summary."""
        if not self.data:
            return {"error": "No data"}

        return {
            "count": len(self.data),
            "mean": self.get_mean(),
            "median": self.get_median(),
            "std_dev": self.get_std_dev(),
            "min_max": self.get_min_max(),
        }

    def clear_data(self):
        """Clear data."""
        self.data = []
        self.metadata = {}
