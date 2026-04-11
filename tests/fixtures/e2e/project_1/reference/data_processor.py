"""
Data Processor Module - Source Reference Implementation
This module demonstrates data processing operations with validation.
"""

import numbers
import statistics
from typing import Annotated, Any, Dict, List, Optional, Union

from pythonarchtesting.rules import forbid_imports

# Type annotations
NumericData = Union[int, float]
DataPoint = Dict[str, Any]


__archtest__: Annotated[
    None,
    forbid_imports(
        "statistics",
        scope="package",
        package="data_processor",
        mode="direct",
    ),
]


class DataProcessor:
    """
    A data processing class for statistical operations and data validation.

    Attributes:
        data (List[NumericData]): Stored numeric data
        metadata (Dict[str, Any]): Additional metadata
    """

    def __init__(self):
        """Initialize data processor with empty data and metadata."""
        self.data: List[NumericData] = []
        self.metadata: Dict[str, Any] = {}

    def add_data_point(self, value: NumericData, label: Optional[str] = None) -> None:
        """
        Add a single data point.

        Args:
            value: Numeric value to add
            label: Optional label for the data point

        Raises:
            TypeError: If value is not numeric
        """
        if not isinstance(value, numbers.Number):
            raise TypeError("Data point must be numeric")

        self.data.append(value)
        if label:
            self.metadata[f"point_{len(self.data)-1}"] = label

    def add_data_batch(self, values: List[NumericData]) -> None:
        """
        Add multiple data points at once.

        Args:
            values: List of numeric values

        Raises:
            TypeError: If any value is not numeric
        """
        for value in values:
            if not isinstance(value, numbers.Number):
                raise TypeError("All data points must be numeric")

        self.data.extend(values)

    def get_mean(self) -> float:
        """
        Calculate mean of the data.

        Returns:
            Mean value of the data

        Raises:
            ValueError: If no data is available
        """
        if not self.data:
            raise ValueError("No data available for calculation")

        return statistics.mean(self.data)

    def get_median(self) -> float:
        """
        Calculate median of the data.

        Returns:
            Median value of the data

        Raises:
            ValueError: If no data is available
        """
        if not self.data:
            raise ValueError("No data available for calculation")

        return statistics.median(self.data)

    def get_std_dev(self) -> float:
        """
        Calculate standard deviation of the data.

        Returns:
            Standard deviation of the data

        Raises:
            ValueError: If no data is available
        """
        if not self.data:
            raise ValueError("No data available for calculation")

        return statistics.stdev(self.data) if len(self.data) > 1 else 0.0

    def get_min_max(self) -> tuple[NumericData, NumericData]:
        """
        Get minimum and maximum values.

        Returns:
            Tuple of (min_value, max_value)

        Raises:
            ValueError: If no data is available
        """
        if not self.data:
            raise ValueError("No data available for calculation")

        return min(self.data), max(self.data)

    def filter_by_range(
        self, min_val: NumericData, max_val: NumericData
    ) -> List[NumericData]:
        """
        Filter data points within specified range.

        Args:
            min_val: Minimum value (inclusive)
            max_val: Maximum value (inclusive)

        Returns:
            List of data points within the range
        """
        return [x for x in self.data if min_val <= x <= max_val]

    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive summary of the data.

        Returns:
            Dictionary with statistical summary
        """
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

    def clear_data(self) -> None:
        """Clear all data and metadata."""
        self.data.clear()
        self.metadata.clear()
