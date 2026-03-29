"""Mock module with complex structure for testing."""

import time
from typing import Any, Dict, List, Optional


class ComplexClass:
    """Complex class with nested logic."""

    def __init__(self, name: str):
        self.name = name
        self._data: List[str] = []
        self._metadata: Dict[str, Any] = {}
        self._created_at = time.time()

    def add_item(self, item: str) -> None:
        """Add an item with validation."""
        if not isinstance(item, str):
            raise ValueError("Item must be a string")
        if len(item) < 1:
            raise ValueError("Item cannot be empty")
        if item in self._data:
            raise ValueError(f"Item '{item}' already exists")

        self._data.append(item)
        self._metadata[item] = {
            "added_at": time.time(),
            "length": len(item),
            "hash": hash(item),
        }

    def get_items(self) -> List[str]:
        """Get all items."""
        return self._data.copy()

    def process_data(self, data: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Process complex data structure."""
        result = {}

        for item in data:
            if "key" in item and "value" in item:
                key = item["key"]
                value = item["value"]

                if key not in result:
                    result[key] = []

                if isinstance(value, list):
                    for v in value:
                        if isinstance(v, str):
                            result[key].append(v.upper())
                        elif isinstance(v, dict):
                            nested_result = self._process_nested_dict(v)
                            result[key].extend(nested_result)
                else:
                    result[key].append(str(value))

        return result

    def _process_nested_dict(self, nested: Dict[str, Any]) -> List[str]:
        """Process nested dictionary."""
        results = []

        for k, v in nested.items():
            if isinstance(v, str):
                results.append(v)
            elif isinstance(v, dict):
                results.extend(self._process_nested_dict(v))
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        results.append(item)

        return results

    def get_metadata(self, item: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an item."""
        return self._metadata.get(item)

    def clear_data(self) -> None:
        """Clear all data."""
        self._data.clear()
        self._metadata.clear()


def complex_function(data: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Complex function with multiple processing steps."""
    processor = ComplexClass("complex_function")

    # First pass: categorize data
    categorized = {}
    for item in data:
        category = item.get("category", "uncategorized")
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(item)

    # Second pass: process each category
    results = {}
    for category, items in categorized.items():
        category_results = []
        for item in items:
            processed = processor.process_data([item])
            for key, values in processed.items():
                if key not in results:
                    results[key] = []
                results[key].extend(values)

        category_results.extend([f"{category}_{v}" for v in values])
        results[category] = category_results

    # Third pass: final processing
    final_results = {}
    for key, values in results.items():
        unique_values = list(set(values))
        unique_values.sort()
        final_results[key] = unique_values

    return final_results


def simple_function(x: int, y: str) -> str:
    """Simple function for comparison."""
    return f"{x}:{y}"
