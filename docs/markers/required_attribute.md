# `required_attribute`

Require a class to expose a named instance or class attribute.

- **Category:** Signature & shape
- **Placement:** class-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import required_attribute
```

Use to assert that a target class exposes a specific attribute by name, with
optional annotation, storage, and descriptor constraints.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `name` (positional) | `str` | — | The attribute name to check on the matched target class. |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `annotation` | `str \| None` | `None` | Expected type annotation as a string; skipped when `None`. |
| `storage` | `str` | `"any"` | Where the attribute must live: `"any"`, `"class"`, or `"instance"`. |
| `allow_property` | `bool` | `False` | Accept a `@property` of the same name as a satisfying attribute. |
| `require_writable` | `bool` | `False` | Require the attribute (or property) to be writable; properties must declare a setter. |
| `declared_only` | `bool` | `False` | Restrict the search to attributes declared on the target class itself, ignoring inherited attributes. |
| `allow_missing` | `bool` | `False` | Pass when no candidate attribute exists on the target instead of failing. |
| `descriptor_kinds` | `tuple[str, ...] \| None` | `None` | Descriptor families to accept (e.g. `"cached_property"`, `"classproperty"`). |
| `include_dynamic_attributes` | `bool` | `False` | Include attributes assigned at runtime via `setattr` or wrappers. |
| `interpret_dataclass_fields` | `bool` | `False` | Treat dataclass fields as instance attributes for matching. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import required_attribute


class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", annotation="str", storage="instance"),
    ]
```

## What it checks

- Presence of an attribute by name on the matched target class.
- Storage location (`class`, `instance`, or either) when `storage` is set.
- Annotation match when `annotation` is provided.
- Optional `@property` acceptance via `allow_property=True`, with optional setter check via `require_writable=True`.
- Optional descriptor kinds (`cached_property`, `classproperty`) and dataclass field interpretation in v2.

## What it does not check

- Attribute default values or runtime assignment values.
- Methods named like getters (e.g., `get_value()`) — those are not attributes.
- Dynamic `setattr(...)` calls unless `include_dynamic_attributes=True` is set.
- Computed names or wrapper-defined descriptors.

## See also

- [../api-reference.md](../api-reference.md) — full option surface, including dataclass and descriptor examples
- [require_member_set](require_member_set.md) — for set-cardinality checks
