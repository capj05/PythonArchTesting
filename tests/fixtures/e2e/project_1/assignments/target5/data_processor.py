"""
Data Processor Module - Target 5 Implementation
Very minimal implementation with many missing features.
"""


class DataProcessor:
    """Basic data processor."""

    def __init__(self):
        self.data = []

    def add_data_point(self, value, label=None):
        self.data.append(value)

    def add_data_batch(self, values):
        self.data.extend(values)

    def get_mean(self):
        if not self.data:
            return 0
        return sum(self.data) / len(self.data)

    # Missing get_median method

    # Missing get_std_dev method

    # Missing get_min_max method

    # Missing filter_by_range method

    # Missing get_summary method

    # Missing clear_data method
