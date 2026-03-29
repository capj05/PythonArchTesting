# Overview

PythonArchTesting analyzes a target project against a reference project with rule declarations. The CLI extracts declaration metadata, compiles supported rules, and evaluates matching entities in each target.

Rule targets are declared with annotations:

```python
from typing import Annotated
from src.rules import required_entity_signature

def normalize(
    value: str,
) -> Annotated[
    str,
    required_entity_signature(mode="compatible", return_annotation="warning"),
]:
    return value.strip().title()
```

Function and method entity rules can live in signatures. Module/class declarations and body-only rule kinds still use `__archtest__: Annotated[...]`. Direct marker factories from `src.rules` are the recommended style, and tuple metadata remains available for compatibility-sensitive reference projects.

## Supported Rules

- `required_entity_signature`: require a matching or compatible top-level function signature.
- `required_method`: require a compatible method declaration.
- `implements_protocol`: require a matched target class to implement a referenced protocol class.
- `forbid_imports`: declare a package or entity import policy.

## Removed Surfaces

These are no longer supported:

- `list_comprehension`
- `[structural_check]`
- `[arch_rules]`
- pattern and anti-pattern decorators

Using the removed config sections now fails validation.
