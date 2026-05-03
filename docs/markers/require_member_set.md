# `require_member_set`

Require a class to expose a set of members (methods, attributes, properties,
descriptors, constructors) that match a name selector and cardinality bounds.

- **Category:** Signature & shape
- **Placement:** class-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import require_member_set
```

Use when the contract is about a **family of members** rather than a specific
named entity. The marker subsumes `require_method_set` and adds attributes,
properties, descriptors, and constructors.

## Arguments

**Required:**

_None — the marker takes only optional arguments._

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `member_kinds` | `tuple[str, ...]` | `("any",)` | Restrict the search to a subset of `{"any", "method", "attribute", "property", "descriptor", "constructor"}`. |
| `name_match` | `str` | `"any"` | Name selector: `"any"`, `"names"`, or `"regex"`. |
| `names` | `list[str] \| None` | `None` | Explicit list of accepted names when `name_match="names"`. |
| `pattern` | `str \| None` | `None` | Regex pattern when `name_match="regex"`. |
| `declared_only` | `bool` | `False` | Restrict the search to members declared on the target class itself, ignoring inherited members. |
| `method_kind` | `str` | `"any"` | Method-kind filter when `member_kinds` includes methods: `"any"`, `"instance"`, `"classmethod"`, or `"staticmethod"`. |
| `storage` | `str` | `"any"` | Attribute storage filter: `"any"`, `"class"`, or `"instance"`. |
| `allow_property` | `bool` | `True` | Accept `@property` definitions when matching attributes. |
| `descriptor_kinds` | `tuple[str, ...] \| None` | `None` | Descriptor families to accept (e.g. `"cached_property"`, `"classproperty"`). |
| `include_dynamic_attributes` | `bool` | `False` | Include attributes assigned at runtime via `setattr` or wrappers. |
| `interpret_dataclass_fields` | `bool` | `False` | Treat dataclass fields as instance attributes. |
| `constructor_kind` | `str` | `"auto"` | Constructor preference when matching constructors: `"auto"`, `"init"`, or `"new"`. |
| `include_dataclass_constructor` | `bool` | `True` | Count statically recognized dataclass-generated `__init__` as a constructor. |
| `min_count` | `int` | `1` | Minimum number of matching members required. |
| `max_count` | `int \| None` | `None` | Maximum number of matching members allowed (no upper bound when `None`). |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import require_member_set


class Contract:
    __archtest__: Annotated[
        None,
        require_member_set(member_kinds=("method", "attribute"), min_count=2),
    ]
```

## What it checks

- Cardinality of the selected member set on the matched target class.
- Selection by `name_match="any"`, `"regex"`, or `"names"`.
- Restriction to subsets of `{"method", "attribute", "property", "descriptor", "constructor"}` via `member_kinds`.
- Optional descriptor families (`cached_property`, `classproperty`) when `member_kinds=("descriptor",)`.

## What it does not check

- Per-member signature or annotation — use the dedicated single-member markers for that.
- Members added at runtime unless `include_dynamic_attributes=True` is set.
- Public/private visibility semantics.

## See also

- [../api-reference.md](../api-reference.md) — full option surface and descriptor examples
- [require_method_set](require_method_set.md) — when you only need methods
- [required_attribute](required_attribute.md), [required_method](required_method.md), [required_constructor](required_constructor.md), [required_factory](required_factory.md) — for individual checks
