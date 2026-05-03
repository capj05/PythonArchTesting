# `required_factory`

Require a class to expose a factory entrypoint — a constructor, a classmethod,
a staticmethod, or a class-body static attribute.

- **Category:** Signature & shape
- **Placement:** factory-capable method body `__archtest__: Annotated[...]` (`__init__`, `__new__`, `@classmethod`, or `@staticmethod`)
## Usage

```python
from pythonarchtesting.rules import required_factory
```

Use when the public way to construct an object is a named classmethod or
staticmethod (e.g., `Session.create(...)`, `User.from_email(...)`). Place the
marker on the source factory method whose contract you want enforced.

## Arguments

**Required:**

_None — the marker takes only optional arguments._

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `signature_mode` | `str` | `"compatible"` | Signature matching mode for the factory: `"compatible"`, `"exact"`, or `"any"`. |
| `satisfy_with` | `tuple[str, ...]` | `("constructor", "classmethod", "staticmethod")` | Accepted candidate kinds; may also include `"static_attribute"`. |
| `allow_inherited` | `bool` | `True` | Accept a factory inherited from a base class as a satisfying candidate. |
| `name_match` | `str` | `"any"` | Name selector: `"exact"`, `"aliases"`, `"regex"`, or `"any"`. |
| `aliases` | `list[str] \| None` | `None` | Accepted alternative names when `name_match="aliases"`. |
| `pattern` | `str \| None` | `None` | Regex pattern when `name_match="regex"`. |
| `allow_missing` | `bool` | `False` | Pass when no candidate factory exists on the target instead of failing. |
| `return_annotation_mode` | `str` | `"auto"` | Return-annotation matching: `"auto"`, `"strict"`, `"compatible"`, or `"ignore"`. |
| `detection_mode` | `str` | `"auto"` | How factories are detected: `"auto"`, `"decorator"`, or `"name"`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import required_factory


class UserService:
    def __init__(self, name: str, value: int):
        __archtest__: Annotated[None, required_factory()]
        self.name = name
        self.value = value
```

## What it checks

- Presence of an accepted factory candidate (constructor, classmethod, staticmethod, or static attribute) under the configured `satisfy_with` and `name_match`.
- Parameter compatibility under `signature_mode`.
- Optional return-annotation matching when `return_annotation_mode != "ignore"`.
- Inherited target candidates when `allow_inherited=True`.

## What it does not check

- Factory body, instantiation logic, or side effects.
- Dynamic registries, service locators, module-level singletons, or runtime descriptor behavior.
- Post-class assignments or `setattr`-defined factories.

## See also

- [../api-reference.md](../api-reference.md) — full option surface and aliases / regex / static-attribute examples
- [required_constructor](required_constructor.md) — when only `__init__` / `__new__` matters
