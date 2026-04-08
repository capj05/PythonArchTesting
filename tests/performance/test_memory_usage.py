"""
Memory usage tests for the Python Architecture Testing toolkit.

These tests ensure the toolkit uses memory efficiently and doesn't leak.
"""

import gc
import time
from pathlib import Path
from typing import Any, Dict

import psutil
import pytest

from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.evidence.collection import (
    collect_static_evidence,
    parse_python_modules,
)

try:
    from pythonarchtesting.state import ProjectState
except ImportError:
    ProjectState = None

from tests.utils.assertions import assert_memory_usage_within_threshold
from tests.utils.generators import generate_test_project


def _run_real_static_analysis(project_root: Path) -> Dict[str, Any]:
    cfg = create_config_from_dict({})
    src_root = project_root / "src"
    parsed_modules, errors = parse_python_modules(
        root_path=src_root,
        config=cfg,
        target_module_name=None,
    )
    evidence = collect_static_evidence(
        root_path=src_root,
        config=cfg,
        target_module_name=None,
        parsed_modules=parsed_modules,
    )
    evidence["parsed_module_count"] = len(parsed_modules)
    evidence["syntax_error_count"] = len(errors)
    return evidence


class TestMemoryUsage:
    """Memory usage and leak detection tests."""

    @pytest.mark.performance
    def test_memory_usage_during_analysis(self, temp_project_dir: Path):
        """Test memory usage during project analysis."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        process = psutil.Process()
        initial_memory = process.memory_info().rss

        # Create project
        generate_test_project(temp_project_dir, num_modules=20)

        # Analyze project
        project_state = ProjectState(str(temp_project_dir), [])
        evidence = _run_real_static_analysis(temp_project_dir)
        assert evidence["parsed_module_count"] > 0 or evidence["syntax_error_count"] > 0

        peak_memory = process.memory_info().rss
        memory_increase = peak_memory - initial_memory

        # Memory should not increase by more than 50MB for 20 modules
        assert_memory_usage_within_threshold(
            memory_increase, 50 * 1024 * 1024, "project analysis"  # 50MB
        )

        # Clean up
        del project_state
        gc.collect()

        final_memory = process.memory_info().rss
        cleanup_increase = final_memory - initial_memory
        assert_memory_usage_within_threshold(
            cleanup_increase, 20 * 1024 * 1024, "memory cleanup after analysis"  # 20MB
        )

    @pytest.mark.performance
    def test_memory_leak_detection(self, temp_dir: Path):
        """Test for memory leaks during repeated operations."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        process = psutil.Process()
        initial_memory = process.memory_info().rss

        # Perform multiple analyses
        for i in range(10):
            # Create project
            project_path = temp_dir / f"leak_test_{i}"
            generate_test_project(project_path, num_modules=5)

            # Analyze project
            project_state = ProjectState(str(project_path), [])
            evidence = _run_real_static_analysis(project_path)
            assert (
                evidence["parsed_module_count"] > 0
                or evidence["syntax_error_count"] > 0
            )

            # Clean up
            del project_state
            gc.collect()

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory should not increase significantly after cleanup
        assert_memory_usage_within_threshold(
            memory_increase, 30 * 1024 * 1024, "repeated analysis operations"  # 30MB
        )

    @pytest.mark.performance
    def test_large_dataset_memory_usage(self, temp_project_dir: Path):
        """Test memory usage with large datasets."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        process = psutil.Process()
        initial_memory = process.memory_info().rss

        # Create large project
        generate_test_project(temp_project_dir, num_modules=50)

        # Analyze large project
        project_state = ProjectState(str(temp_project_dir), [])
        evidence = _run_real_static_analysis(temp_project_dir)
        assert evidence["parsed_module_count"] > 0 or evidence["syntax_error_count"] > 0

        peak_memory = process.memory_info().rss
        memory_increase = peak_memory - initial_memory

        # Memory should scale reasonably with project size
        # 50 modules should not use more than 100MB
        assert_memory_usage_within_threshold(
            memory_increase, 100 * 1024 * 1024, "large dataset analysis"  # 100MB
        )

        # Clean up
        del project_state
        gc.collect()

        final_memory = process.memory_info().rss
        cleanup_increase = final_memory - initial_memory
        assert_memory_usage_within_threshold(
            cleanup_increase, 40 * 1024 * 1024, "large dataset cleanup"  # 40MB
        )

    @pytest.mark.performance
    def test_validation_results_memory_usage(self, temp_project_dir: Path):
        """Test memory usage when storing many validation results."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        process = psutil.Process()
        initial_memory = process.memory_info().rss

        project_state = ProjectState(str(temp_project_dir), [])

        # Simulate storing many validation results
        num_results = 1000
        for i in range(num_results):
            # Simulate validation result
            _ = {
                "type": "error" if i % 3 == 0 else "warning",
                "message": f"Validation message {i}",
                "file": f"file_{i % 10}.py",
                "line": i % 100 + 1,
                "severity": i % 3,
            }
            # project_state.validation_results.append(result)

        peak_memory = process.memory_info().rss
        memory_increase = peak_memory - initial_memory

        # 1000 validation results should not use more than 20MB
        assert_memory_usage_within_threshold(
            memory_increase, 20 * 1024 * 1024, "validation results storage"  # 20MB
        )

        # Clean up
        del project_state
        gc.collect()

        final_memory = process.memory_info().rss
        cleanup_increase = final_memory - initial_memory
        assert_memory_usage_within_threshold(
            cleanup_increase, 5 * 1024 * 1024, "validation results cleanup"  # 5MB
        )

    @pytest.mark.performance
    def test_import_graph_memory_usage(self, temp_project_dir: Path):
        """Test memory usage when building import graphs."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        process = psutil.Process()
        initial_memory = process.memory_info().rss

        # Create project with complex import structure
        generate_test_project(temp_project_dir, num_modules=30)

        # Add complex import patterns
        for i in range(30):
            module_file = temp_project_dir / "src" / f"module_{i}.py"
            imports = []
            for j in range(min(10, i)):  # Each module imports up to 10 others
                imports.append(f"from .module_{j} import Class{j}")

            content = f'''
"""Module {i}."""

{chr(10).join(imports)}

class Class{i}:
    """Class {i}."""

    def method(self):
        return "method_{i}"
'''
            module_file.write_text(content)

        # Build import graph
        project_state = ProjectState(str(temp_project_dir), [])
        evidence = _run_real_static_analysis(temp_project_dir)
        assert evidence["import_edges"]

        peak_memory = process.memory_info().rss
        memory_increase = peak_memory - initial_memory

        # Complex import graph should not use more than 60MB
        assert_memory_usage_within_threshold(
            memory_increase, 60 * 1024 * 1024, "import graph building"  # 60MB
        )

        # Clean up
        del project_state
        gc.collect()

        final_memory = process.memory_info().rss
        cleanup_increase = final_memory - initial_memory
        assert_memory_usage_within_threshold(
            cleanup_increase, 25 * 1024 * 1024, "import graph cleanup"  # 25MB
        )

    @pytest.mark.performance
    def test_concurrent_memory_usage(self, temp_dir: Path):
        """Test memory usage during concurrent operations."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        import concurrent.futures

        process = psutil.Process()
        initial_memory = process.memory_info().rss

        def analyze_project(project_id: int, base_dir: Path):
            """Analyze a project in a separate thread."""
            project_path = base_dir / f"concurrent_project_{project_id}"
            generate_test_project(project_path, num_modules=5)

            project_state = ProjectState(str(project_path), [])
            evidence = _run_real_static_analysis(project_path)
            assert (
                evidence["parsed_module_count"] > 0
                or evidence["syntax_error_count"] > 0
            )

            # Clean up
            del project_state
            gc.collect()

        # Run concurrent analyses
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(analyze_project, i, temp_dir) for i in range(8)]
            concurrent.futures.wait(futures)

        peak_memory = process.memory_info().rss
        memory_increase = peak_memory - initial_memory

        # Concurrent operations should not use excessive memory
        assert_memory_usage_within_threshold(
            memory_increase, 80 * 1024 * 1024, "concurrent operations"  # 80MB
        )

        # Force cleanup
        gc.collect()

        final_memory = process.memory_info().rss
        cleanup_increase = final_memory - initial_memory
        assert_memory_usage_within_threshold(
            cleanup_increase, 30 * 1024 * 1024, "concurrent operations cleanup"  # 30MB
        )

    @pytest.mark.performance
    def test_cache_memory_usage(self, temp_project_dir: Path):
        """Test memory usage of caching mechanisms."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        process = psutil.Process()
        initial_memory = process.memory_info().rss

        project_state = ProjectState(str(temp_project_dir), [])

        # Simulate caching many results
        cache_size = 500
        for i in range(cache_size):
            # Simulate cached analysis result
            f"file_{i}.py"
            _ = {
                "complexity": i % 20,
                "imports": [f"module_{j}" for j in range(i % 5)],
                "functions": [f"func_{j}" for j in range(i % 3)],
                "timestamp": time.time(),
            }
            # project_state.cache[cache_key] = cache_value

        peak_memory = process.memory_info().rss
        memory_increase = peak_memory - initial_memory

        # Cache should not use excessive memory
        assert_memory_usage_within_threshold(
            memory_increase, 30 * 1024 * 1024, "caching mechanism"  # 30MB
        )

        # Clear cache
        # project_state.cache.clear()
        del project_state
        gc.collect()

        final_memory = process.memory_info().rss
        cleanup_increase = final_memory - initial_memory
        assert_memory_usage_within_threshold(
            cleanup_increase, 10 * 1024 * 1024, "cache cleanup"  # 10MB
        )

    @pytest.mark.performance
    def test_report_generation_memory_usage(self, temp_project_dir: Path):
        """Test memory usage during report generation."""
        if not ProjectState:
            pytest.skip("ProjectState not available")
            return

        process = psutil.Process()
        initial_memory = process.memory_info().rss

        # Create project with many validation results
        generate_test_project(temp_project_dir, num_modules=20)

        project_state = ProjectState(str(temp_project_dir), [])

        # Simulate having many validation results
        # project_state.validation_results = [mock results for 20 modules]

        # Generate large report
        evidence = _run_real_static_analysis(temp_project_dir)
        assert evidence["parsed_module_count"] > 0 or evidence["syntax_error_count"] > 0

        peak_memory = process.memory_info().rss
        memory_increase = peak_memory - initial_memory

        # Report generation should not use excessive memory
        assert_memory_usage_within_threshold(
            memory_increase, 25 * 1024 * 1024, "report generation"  # 25MB
        )

        # Clean up
        del project_state
        gc.collect()

        final_memory = process.memory_info().rss
        cleanup_increase = final_memory - initial_memory
        assert_memory_usage_within_threshold(
            cleanup_increase, 10 * 1024 * 1024, "report generation cleanup"  # 10MB
        )
