"""
Project/code generators used by integration and performance tests.
"""

from __future__ import annotations

import json
import random
import string
from pathlib import Path
from typing import Any, Dict, List, Optional


def generate_random_string(length: int = 10, prefix: str = "") -> str:
    """
    Generate a random string with optional prefix.
    """
    random_part = "".join(
        random.choices(string.ascii_lowercase + string.digits, k=length)
    )
    return f"{prefix}{random_part}" if prefix else random_part


def generate_python_function(
    name: str, args: Optional[List[str]] = None, complexity_level: str = "simple"
) -> str:
    """
    Generate a Python function with specified complexity.
    """
    if args is None:
        args = ["data"]

    arg_string = ", ".join(args)

    if complexity_level == "simple":
        return f'''
def {name}({arg_string}):
    """Simple function for testing."""
    return "processed"
'''

    if complexity_level == "medium":
        return f'''
def {name}({arg_string}):
    """Medium complexity function for testing."""
    result = []
    for item in data:
        if isinstance(item, str):
            result.append(item.upper())
        elif isinstance(item, (int, float)):
            result.append(item * 2)
        else:
            result.append(str(item))
    return result
'''

    if complexity_level == "complex":
        return f'''
def {name}({arg_string}):
    """Complex function for testing."""
    result = {{}}
    nested_data = []

    # First pass: categorize data
    for item in data:
        if isinstance(item, dict):
            for key, value in item.items():
                if key not in result:
                    result[key] = []
                if isinstance(value, list):
                    for v in value:
                        if isinstance(v, str):
                            result[key].append(v.upper())
                        elif isinstance(v, dict):
                            nested_result = process_nested_dict(v)
                            result[key].extend(nested_result)
                else:
                    result[key].append(str(value))
        elif isinstance(item, (list, tuple)):
            nested_data.extend(item)
        else:
            nested_data.append(item)

    # Second pass: process nested data
    if nested_data:
        result["nested"] = process_nested_data(nested_data)

    return result

def process_nested_dict(nested):
    """Process nested dictionary."""
    results = []
    for k, v in nested.items():
        if isinstance(v, str):
            results.append(v)
        elif isinstance(v, dict):
            results.extend(process_nested_dict(v))
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    results.append(item)
    return results

def process_nested_data(data):
    """Process nested data."""
    return [str(item) for item in data if item is not None]
'''

    raise ValueError(f"Unknown complexity level: {complexity_level}")


def generate_python_class(
    name: str, methods: Optional[List[str]] = None, include_properties: bool = False
) -> str:
    """
    Generate a Python class with specified methods.
    """
    if methods is None:
        methods = ["__init__", "process", "validate"]

    class_code = f'''
class {name}:
    """Generated class for testing."""

    def __init__(self):
        """Initialize the {name}."""
        self.name = "{name}"
        self._data = []
'''

    if include_properties:
        class_code += '''
    @property
    def data(self):
        """Get the data."""
        return self._data.copy()

    @data.setter
    def data(self, value):
        """Set the data."""
        if isinstance(value, list):
            self._data = value
        else:
            raise ValueError("Data must be a list")
'''

    for method in methods:
        if method == "__init__":
            continue

        method_code = f'''
    def {method}(self, *args, **kwargs):
        """{method.title()} method."""
        return f"{method}_result"
'''
        class_code += method_code

    return class_code


def generate_python_module(
    module_name: str,
    functions: Optional[List[Dict[str, Any]]] = None,
    classes: Optional[List[Dict[str, Any]]] = None,
    imports: Optional[List[str]] = None,
) -> str:
    """
    Generate a complete Python module.
    """
    module_code = f'''"""
Generated module {module_name} for testing.
'''

    if imports:
        module_code += "\n".join(imports) + "\n\n"

    if functions:
        for func_spec in functions:
            func_name = func_spec.get("name", f"function_{
                generate_random_string(5)}")
            func_args = func_spec.get("args", ["data"])
            complexity = func_spec.get("complexity", "simple")

            module_code += generate_python_function(func_name, func_args, complexity)
            module_code += "\n"

    if classes:
        for class_spec in classes:
            class_name = class_spec.get("name", f"TestClass{
                generate_random_string(5)}")
            methods = class_spec.get("methods", ["process", "validate"])
            include_props = class_spec.get("include_properties", False)

            module_code += generate_python_class(class_name, methods, include_props)
            module_code += "\n"

    return module_code


def generate_test_project(
    base_dir: Path,
    num_modules: int = 3,
    complexity_distribution: Optional[Dict[str, int]] = None,
    include_circular_imports: bool = False,
) -> Dict[str, Any]:
    """
    Generate a complete test project with multiple modules.
    """
    if complexity_distribution is None:
        complexity_distribution = {"simple": 60, "medium": 30, "complex": 10}

    base_dir.mkdir(parents=True, exist_ok=True)

    src_dir = base_dir / "src"
    tests_dir = base_dir / "tests"
    docs_dir = base_dir / "docs"

    for dir_path in [src_dir, tests_dir, docs_dir]:
        dir_path.mkdir(exist_ok=True)
        (dir_path / "__init__.py").touch()

    modules = {}
    module_names = [f"module_{i}" for i in range(num_modules)]

    for i, module_name in enumerate(module_names):
        functions = []
        classes = []

        num_functions = random.randint(2, 5)
        for j in range(num_functions):
            complexity = random.choices(
                list(complexity_distribution.keys()),
                weights=list(complexity_distribution.values()),
            )[0]

            functions.append(
                {
                    "name": f"function_{module_name.split('_')[1]}_{j}",
                    "args": ["data", "options"],
                    "complexity": complexity,
                }
            )

        num_classes = random.randint(1, 3)
        for j in range(num_classes):
            classes.append(
                {
                    "name": f"Class{module_name.split('_')[1].title()}{j}",
                    "methods": ["process", "validate", "transform"],
                    "include_properties": random.choice([True, False]),
                }
            )

        imports = ["from typing import List, Dict, Any, Optional"]
        if i > 0:
            prev_module = module_names[i - 1]
            imports.append(f"from .{prev_module} import {
                prev_module.split('_')[1].title()}")

        if include_circular_imports and i == num_modules - 1:
            imports.append(f"from .{
                module_names[0]} import {
                module_names[0].split('_')[1].title()}")

        module_code = generate_python_module(module_name, functions, classes, imports)

        module_file = src_dir / f"{module_name}.py"
        module_file.write_text(module_code)

        modules[module_name] = {
            "file_path": module_file,
            "functions": functions,
            "classes": classes,
            "imports": imports,
        }

    main_code = '''"""
Main module for generated test project.
"""

from typing import List, Dict, Any

'''

    for module_name in module_names:
        module_short = module_name.split("_")[1]
        main_code += f"from .{module_name} import {module_short.title()}\n"

    main_code += """
class MainApplication:
    \"\"\"Main application class.\"\"\"

    def __init__(self):
        \"\"\"Initialize the application.\"\"\"
        self.components = []
"""

    for module_name in module_names:
        module_short = module_name.split("_")[1]
        main_code += f"        self.components.append({
            module_short.title()}())\n"

    main_code += """
    def run(self, data: Any) -> Dict[str, Any]:
        \"\"\"Run the application.\"\"\"
        results = {}
        for component in self.components:
            if hasattr(component, 'process'):
                results[component.__class__.__name__] = component.process(data)
        return results
"""

    main_file = src_dir / "main.py"
    main_file.write_text(main_code)

    config = {
        "project": {
            "name": f"generated_project_{
                generate_random_string(6)}",
            "version": "1.0.0",
            "description": "Generated test project for architecture validation",
        },
        "validation": {
            "rules": [
                {
                    "name": "no_circular_imports",
                    "type": "import_analysis",
                    "enabled": not include_circular_imports,
                },
                {
                    "name": "max_complexity",
                    "type": "complexity_analysis",
                    "enabled": True,
                    "threshold": 15,
                },
            ]
        },
        "reporting": {"format": "json", "output": "validation_report.json"},
    }

    config_file = base_dir / "config.json"
    config_file.write_text(json.dumps(config, indent=2))

    return {
        "base_dir": base_dir,
        "modules": modules,
        "main_file": main_file,
        "config_file": config_file,
        "config": config,
        "has_circular_imports": include_circular_imports,
    }


__all__ = [
    "generate_random_string",
    "generate_python_function",
    "generate_python_class",
    "generate_python_module",
    "generate_test_project",
]
