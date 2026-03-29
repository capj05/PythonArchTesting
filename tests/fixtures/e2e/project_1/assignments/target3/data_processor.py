"""
Data Processor Module - Target 3 Implementation
Good implementation but missing some features and type hints.
"""

import statistics


class DataProcessor:
    """
    Data processor for statistical operations.
    """

    def __init__(self):
        """Initialize data processor."""
        self.data = []
        self.metadata = {}

    def add_data_point(self, value, label=None):
        """Add a single data point."""
        if not isinstance(value, (int, float)):
            raise TypeError("Value must be numeric")
        self.data.append(value)
        if label:
            self.metadata[f"point_{len(self.data)-1}"] = label

    def add_data_batch(self, values):
        """Add multiple data points."""
        for value in values:
            if not isinstance(value, (int, float)):
                raise TypeError("All values must be numeric")
        self.data.extend(values)

    def get_mean(self):
        """Calculate mean of the data."""
        if not self.data:
            raise ValueError("No data available")
        import statistics

        return statistics.mean(self.data)

    def get_median(self):
        """Calculate median of the data."""
        if not self.data:
            raise ValueError("No data available")
        return statistics.median(self.data)

    def get_std_dev(self):
        """Calculate standard deviation."""
        if not self.data:
            raise ValueError("No data available")
        if len(self.data) <= 1:
            return 0.0
        return statistics.stdev(self.data)

    def get_min_max(self):
        """Get minimum and maximum values."""
        if not self.data:
            raise ValueError("No data available")
        return (min(self.data), max(self.data))

    def filter_by_range(self, min_val, max_val):
        """Filter data within range."""
        return [x for x in self.data if min_val <= x <= max_val]

    def get_summary(self):
        """Get comprehensive summary."""
        if not self.data:
            return {"error": "No data available"}

        return {
            "count": len(self.data),
            "mean": self.get_mean(),
            "median": self.get_median(),
            "std_dev": self.get_std_dev(),
            "min_max": self.get_min_max(),
            "metadata": self.metadata.copy(),
        }

    def clear_data(self):
        """Clear all data."""
        self.data.clear()
        self.metadata.clear()
