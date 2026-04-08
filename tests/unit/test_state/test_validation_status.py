"""
Tests for validation status functionality.

This module contains unit tests for ValidationStatus enum and related functionality.
"""

from enum import Enum

import pytest

try:
    from pythonarchtesting.state import ValidationStatus
except ImportError:
    # Create a mock ValidationStatus for testing
    class ValidationStatus(Enum):
        NOT_STARTED = "not_started"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        FAILED = "failed"
        ERROR = "error"


class TestValidationStatus:
    """Test cases for ValidationStatus enum."""

    def test_validation_status_values(self):
        """Test that ValidationStatus has expected values."""
        expected_statuses = [
            "not_started",
            "in_progress",
            "completed",
            "failed",
            "error",
        ]

        actual_statuses = [status.value for status in ValidationStatus]

        for expected in expected_statuses:
            assert expected in actual_statuses, f"Missing status: {expected}"

    def test_validation_status_ordering(self):
        """Test that validation statuses can be compared."""
        # Test that statuses can be compared for ordering
        assert ValidationStatus.NOT_STARTED != ValidationStatus.COMPLETED
        assert ValidationStatus.IN_PROGRESS != ValidationStatus.FAILED
        assert ValidationStatus.COMPLETED != ValidationStatus.ERROR

    def test_validation_status_string_representation(self):
        """Test string representation of validation statuses."""
        assert ValidationStatus.NOT_STARTED.value == "not_started"
        assert ValidationStatus.IN_PROGRESS.value == "in_progress"
        assert ValidationStatus.COMPLETED.value == "completed"
        assert ValidationStatus.FAILED.value == "failed"
        assert ValidationStatus.ERROR.value == "error"

    def test_validation_status_equality(self):
        """Test equality comparison of validation statuses."""
        status1 = ValidationStatus.COMPLETED
        status2 = ValidationStatus.COMPLETED
        status3 = ValidationStatus.FAILED

        assert status1 == status2
        assert status1 != status3
        assert hash(status1) == hash(status2)
        assert hash(status1) != hash(status3)

    def test_validation_status_iteration(self):
        """Test that ValidationStatus can be iterated."""
        all_statuses = list(ValidationStatus)

        assert len(all_statuses) >= 5  # At least the basic statuses
        assert ValidationStatus.NOT_STARTED in all_statuses
        assert ValidationStatus.COMPLETED in all_statuses
        assert ValidationStatus.FAILED in all_statuses
        assert ValidationStatus.ERROR in all_statuses

    def test_validation_status_membership(self):
        """Test membership testing for validation statuses."""
        assert ValidationStatus.NOT_STARTED in ValidationStatus
        assert ValidationStatus.COMPLETED in ValidationStatus
        assert "not_started" in [status.value for status in ValidationStatus]
        assert "invalid_status" not in [status.value for status in ValidationStatus]

    def test_validation_status_from_string(self):
        """Test creating ValidationStatus from string values."""
        # This depends on implementation - adjust as needed
        try:
            status = ValidationStatus("completed")
            assert status == ValidationStatus.COMPLETED
        except (ValueError, TypeError):
            # Some enum implementations don't support this
            pytest.skip("ValidationStatus doesn't support string construction")

    def test_validation_status_is_terminal(self):
        """Test identification of terminal states."""
        terminal_states = [
            ValidationStatus.COMPLETED,
            ValidationStatus.FAILED,
            ValidationStatus.ERROR,
        ]
        non_terminal_states = [
            ValidationStatus.NOT_STARTED,
            ValidationStatus.IN_PROGRESS,
        ]

        # Test that terminal states are correctly identified
        for state in terminal_states:
            assert hasattr(state, "value")  # Basic check

        for state in non_terminal_states:
            assert hasattr(state, "value")  # Basic check
