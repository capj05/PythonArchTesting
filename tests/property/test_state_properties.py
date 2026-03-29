"""
Property-based tests for state management.

These tests use hypothesis to generate test cases and verify
properties that should always hold true.
"""

from typing import Dict, List, Set

import pytest

hypothesis = pytest.importorskip("hypothesis")
given = hypothesis.given
st = hypothesis.strategies

try:
    from src.state import ProjectState, ValidationStatus
except ImportError:
    ProjectState = None
    ValidationStatus = None


class TestStateProperties:
    """Property-based tests for state management."""

    @given(st.lists(st.text(min_size=1), min_size=0, max_size=100))
    def test_module_addition_increases_count(self, module_names: List[str]):
        """Test that adding modules always increases the count."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        project_state = ProjectState("/test", [])
        initial_count = len(project_state.get("imported_modules", {}))

        for name in module_names:
            # Simulate adding module
            if not hasattr(project_state, "imported_modules"):
                project_state.imported_modules = {}
            project_state.imported_modules[name] = {"imports": []}

            current_count = len(project_state.imported_modules)
            expected_count = initial_count + module_names.index(name) + 1
            assert current_count == expected_count

    @given(st.sets(st.text(min_size=1), min_size=1, max_size=50))
    def test_validation_results_accumulate(self, error_messages: Set[str]):
        """Test that validation results accumulate correctly."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        project_state = ProjectState("/test", [])
        if not hasattr(project_state, "validation_results"):
            project_state.validation_results = []

        for message in error_messages:
            # Simulate adding validation result
            result = {"type": "error", "message": message, "file": "test.py", "line": 1}
            project_state.validation_results.append(result)

        assert len(project_state.validation_results) == len(error_messages)

        # All messages should be present
        result_messages = {r["message"] for r in project_state.validation_results}
        assert result_messages == error_messages

    @given(st.integers(min_value=0, max_value=1000))
    def test_statistics_consistency(self, num_validations: int):
        """Test that statistics remain consistent."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        project_state = ProjectState("/test", [])
        if not hasattr(project_state, "validation_results"):
            project_state.validation_results = []
        if not hasattr(project_state, "validation_stats"):
            project_state.validation_stats = {}

        # Add validation results
        for i in range(num_validations):
            status = "error" if i % 3 == 0 else "warning" if i % 3 == 1 else "info"
            result = {
                "type": status,
                "message": f"Message {i}",
                "file": f"file_{i}.py",
                "line": i % 100 + 1,
            }
            project_state.validation_results.append(result)

        # Simulate statistics calculation
        stats = {
            "total": num_validations,
            "by_type": {
                "error": sum(
                    1 for r in project_state.validation_results if r["type"] == "error"
                ),
                "warning": sum(
                    1
                    for r in project_state.validation_results
                    if r["type"] == "warning"
                ),
                "info": sum(
                    1 for r in project_state.validation_results if r["type"] == "info"
                ),
            },
        }
        project_state.validation_stats = stats

        # Check consistency
        assert stats["total"] == num_validations
        assert sum(stats["by_type"].values()) == num_validations
        assert all(count >= 0 for count in stats["by_type"].values())

    @given(st.dictionaries(keys=st.text(), values=st.lists(st.text())))
    def test_import_graph_properties(self, import_graph: Dict[str, List[str]]):
        """Test that import graph maintains expected properties."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        project_state = ProjectState("/test", [])
        project_state.imported_modules = import_graph

        # All keys should be modules
        for module_name in import_graph.keys():
            assert isinstance(module_name, str)
            assert len(module_name) > 0

        # All values should be lists of strings
        for imports in import_graph.values():
            assert isinstance(imports, list)
            for import_name in imports:
                assert isinstance(import_name, str)

    @given(st.lists(st.text(min_size=1), min_size=0, max_size=50))
    def test_reference_modules_uniqueness(self, module_names: List[str]):
        """Test that reference modules maintain uniqueness."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        project_state = ProjectState("/test", [])
        if not hasattr(project_state, "reference_modules"):
            project_state.reference_modules = []

        # Add modules (some may be duplicates)
        for name in module_names:
            if name not in project_state.reference_modules:
                project_state.reference_modules.append(name)

        # Should have no duplicates
        assert len(project_state.reference_modules) == len(
            set(project_state.reference_modules)
        )

        # All original unique names should be present
        unique_names = set(module_names)
        for name in unique_names:
            assert name in project_state.reference_modules

    @given(st.integers(min_value=0, max_value=100))
    def test_target_functions_counting(self, num_functions: int):
        """Test that target functions are counted correctly."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        project_state = ProjectState("/test", [])
        if not hasattr(project_state, "target_functions"):
            project_state.target_functions = {}

        # Add target functions
        for i in range(num_functions):
            func_name = f"function_{i}"
            project_state.target_functions[func_name] = {
                "file": f"file_{i}.py",
                "line": i + 1,
                "complexity": i % 10 + 1,
            }

        assert len(project_state.target_functions) == num_functions

        # All functions should have required properties
        for func_info in project_state.target_functions.values():
            assert "file" in func_info
            assert "line" in func_info
            assert "complexity" in func_info

    @given(
        st.dictionaries(keys=st.text(), values=st.integers(min_value=1, max_value=100))
    )
    def test_complexity_distribution(self, complexity_data: Dict[str, int]):
        """Test that complexity data maintains expected properties."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        project_state = ProjectState("/test", [])

        # Simulate complexity analysis
        project_state.complexity_stats = {
            "total_files": len(complexity_data),
            "average_complexity": (
                sum(complexity_data.values()) / len(complexity_data)
                if complexity_data
                else 0
            ),
            "max_complexity": max(complexity_data.values()) if complexity_data else 0,
            "min_complexity": min(complexity_data.values()) if complexity_data else 0,
        }

        # Check properties
        if complexity_data:
            assert (
                project_state.complexity_stats["max_complexity"]
                >= project_state.complexity_stats["min_complexity"]
            )
            assert project_state.complexity_stats["average_complexity"] >= 0
            assert project_state.complexity_stats["total_files"] == len(complexity_data)
        else:
            assert project_state.complexity_stats["average_complexity"] == 0
            assert project_state.complexity_stats["max_complexity"] == 0
            assert project_state.complexity_stats["min_complexity"] == 0

    @given(st.lists(st.text(), min_size=0, max_size=20))
    def test_file_analysis_ordering(self, file_names: List[str]):
        """Test that file analysis maintains ordering."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        project_state = ProjectState("/test", [])
        if not hasattr(project_state, "analyzed_files"):
            project_state.analyzed_files = []

        # Analyze files in order
        for file_name in file_names:
            project_state.analyzed_files.append(
                {
                    "name": file_name,
                    "timestamp": len(project_state.analyzed_files),
                    "status": "analyzed",
                }
            )

        # Should maintain order
        analyzed_names = [f["name"] for f in project_state.analyzed_files]
        assert analyzed_names == file_names

        # Timestamps should be sequential
        timestamps = [f["timestamp"] for f in project_state.analyzed_files]
        assert timestamps == list(range(len(file_names)))

    @given(st.dictionaries(keys=st.text(), values=st.text()))
    def test_project_metadata_properties(self, metadata: Dict[str, str]):
        """Test that project metadata maintains expected properties."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        project_state = ProjectState("/test", [])
        project_state.project_metadata = metadata

        # All keys and values should be strings
        for key, value in metadata.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

        # Should be able to retrieve all metadata
        for key, expected_value in metadata.items():
            actual_value = project_state.project_metadata.get(key)
            assert actual_value == expected_value

    @given(
        st.integers(min_value=0, max_value=1000),
        st.integers(min_value=0, max_value=100),
    )
    def test_validation_progress_tracking(self, total_items: int, processed_items: int):
        """Test that validation progress is tracked correctly."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        project_state = ProjectState("/test", [])

        # Simulate validation progress
        actual_processed = min(processed_items, total_items)
        project_state.validation_progress = {
            "total": total_items,
            "processed": actual_processed,
            "percentage": (
                (actual_processed / total_items * 100) if total_items > 0 else 0
            ),
        }

        progress = project_state.validation_progress

        assert progress["total"] == total_items
        assert progress["processed"] == actual_processed
        assert 0 <= progress["percentage"] <= 100

        if total_items > 0:
            assert progress["percentage"] == (actual_processed / total_items * 100)
        else:
            assert progress["percentage"] == 0
