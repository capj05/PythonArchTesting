"""
Data Processor Module - Target 2 Implementation
Incomplete implementation with several issues.
"""


class DataProcessor:
    """Data processor with basic functionality."""

    def __init__(self):
        self.data = []

    def add_data_point(self, value, label=None):
        """Add single data point."""
        self.data.append(value)

    def add_data_batch(self, values):
        """Add batch of data points."""
        for value in values:
            self.data.append(value)

    def get_mean(self):
        """Calculate mean."""
        if len(self.data) == 0:
            return 0
        return sum(self.data) / len(self.data)

    def get_median(self):
        """Calculate median - incorrect implementation."""
        return self.data[len(self.data) // 2] if self.data else 0

    def get_std_dev(self):
        """Standard deviation - not implemented."""
        return 0

    def get_min_max(self):
        """Get min and max."""
        if not self.data:
            return (0, 0)
        return (min(self.data), max(self.data))

    def filter_by_range(self, min_val, max_val):
        """Filter by range."""
        result = []
        for x in self.data:
            if x >= min_val and x <= max_val:
                result.append(x)
        return result

    def get_summary(self):
        """Get summary - missing some fields."""
        return {
            "count": len(self.data),
            "mean": self.get_mean(),
            "min": self.get_min_max()[0],
            "max": self.get_min_max()[1],
        }

    def clear_data(self):
        """Clear data."""
        self.data = []
