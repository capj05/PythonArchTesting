# `does_not_have`

Forbid a method, attribute, or property by name on the matched target class.

- **Category:** Signature & shape
- **Placement:** class-body `__archtest__: Annotated[...]`, or method-body `__archtest__: Annotated[...]` to derive `name` from the source method
## Usage

```python
from pythonarchtesting.rules import does_not_have
```

Use to assert a member is **absent** on the matched target class — whether by
exact name, alias list, or regex pattern. A method-body declaration derives
`name` (and optional `signature_mode`) from the source method.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `name` (positional) | `str \| None` | `None` | Member name to forbid; required for `name_match="exact"` outside method-body declarations, where the source method name is used implicitly. |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `member_kind` | `str` | `"any"` | Kind of forbidden member: `"any"`, `"method"`, `"attribute"`, `"property"`, `"descriptor"`, or `"constructor"`. |
| `storage` | `str` | `"any"` | Attribute storage filter when forbidding attributes: `"any"`, `"class"`, or `"instance"`. |
| `declared_only` | `bool` | `False` | Restrict the search to members declared on the target class itself, ignoring inherited members. |
| `name_match` | `str` | `"exact"` | Name selector: `"exact"`, `"aliases"`, or `"regex"`. |
| `aliases` | `list[str] \| None` | `None` | Accepted alternative names when `name_match="aliases"`. |
| `pattern` | `str \| None` | `None` | Regex pattern when `name_match="regex"`. |
| `signature_mode` | `str` | `"any"` | Signature filter for forbidden methods: `"any"`, `"compatible"`, or `"exact"`. |
| `include_descriptors` | `bool` | `False` | Include descriptor-based members in the absence check. |
| `include_dynamic_attributes` | `bool` | `False` | Include attributes assigned at runtime via `setattr` or wrappers. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import does_not_have


class Repository:
    __archtest__: Annotated[
        None,
        does_not_have("debug_dump", member_kind="method"),
    ]
```

## What it checks

- Absence of a matching member on the matched target class under the configured `member_kind` and `name_match`.
- Optional method signature mode for forbidden methods (`compatible` / `exact` / `any`).
- Inherited members count by default; restrict with `declared_only=True`.

## What it does not check

- Import absence — use [forbid_imports](forbid_imports.md).
- Public/private visibility semantics.
- Dynamic attributes unless `include_dynamic_attributes=True`.
- Descriptors unless `include_descriptors=True`.

## See also

- [../api-reference.md](../api-reference.md) — full option surface and alias/regex/method-body examples
- [forbid_imports](forbid_imports.md) — for import absence
