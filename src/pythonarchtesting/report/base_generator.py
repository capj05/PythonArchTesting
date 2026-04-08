"""
Base class for report generators.

This module provides an abstract base class that all report generators
should inherit from, ensuring consistent interface and behavior.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pythonarchtesting.constants import ReportingConstants


class BaseReportGenerator(ABC):
    """Abstract base class for all report generators."""

    def __init__(self, report_data: Any):
        """
        Initialize the report generator.

        Args:
            report_data: Canonical report dict or ProjectState instance
        """
        self._state = None
        self.report: Optional[Dict[str, Any]] = None
        if isinstance(report_data, dict):
            self.report = report_data
        else:
            self._state = report_data
        self.include_sections: List[str] = []

    def generate(
        self,
        include_sections: Optional[List[str]] = None,
        output_file: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate report in the specific format.

        Args:
            include_sections: Optional list of sections to include in reports

        Returns:
            The generated report as a string
        """
        self.include_sections = include_sections or []
        del kwargs
        return self._generate_report(output_file=output_file)

    def _ensure_report(self) -> Dict[str, Any]:
        if self.report is None:
            if self._state is None:
                raise ValueError("Report data is not available.")

            # Lazy import to avoid circular dependency
            from pythonarchtesting.report.api import build_report

            self.report = build_report(self._state)
        return self.report

    @abstractmethod
    def _generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate report content for the concrete format."""
        raise NotImplementedError

    def _get_status_icon(self, status_value: str) -> str:
        """
        Get the appropriate icon for a validation status.

        Args:
            status_value: The string value of the validation status

        Returns:
            Icon string for the status
        """
        return ReportingConstants.STATUS_ICONS.get(status_value, "❓")

    def _truncate_description(
        self, description: str, max_length: Optional[int] = None
    ) -> str:
        """
        Truncate description if too long.

        Args:
            description: The description to truncate
            max_length: Maximum length before truncation (uses constant if not provided)

        Returns:
            Truncated description with ellipsis if needed
        """
        if max_length is None:
            max_length = ReportingConstants.MAX_DESCRIPTION_LENGTH

        if len(description) > max_length:
            return description[: max_length - 3] + "..."
        return description

    def _format_file_link(self, file_path: str, line_num: Optional[int] = None) -> str:
        """
        Format file path as a markdown link with line number.

        Args:
            file_path: Path to the source file
            line_num: Optional line number

        Returns:
            Formatted file link
        """
        if not file_path:
            return "N/A"

        link = f"[{file_path}]({file_path})"
        if line_num:
            link += f":{line_num}"
        return link

    def _count_statuses(self, results: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for item in results:
            status = str(item.get("status") or "")
            counts[status] = counts.get(status, 0) + 1
        return counts
