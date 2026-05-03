# `require_method_set`

Require a class to expose a set of methods that match a name selector and
optional cardinality bounds.

- **Category:** Signature & shape
- **Placement:** class-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import require_method_set
```

Use when you care about **how many** methods match a pattern, not the exact
shape of any one method. Examples: every test class must have at least one
`test_*` method; every lifecycle class must declare `setUp` and `tearDown`.

## Arguments

**Required:**

_None — the marker takes only optional arguments._

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `name_match` | `str` | `"any"` | Name selector: `"any"`, `"names"`, or `"regex"`. |
| `names` | `list[str] \| None` | `None` | Explicit list of accepted names when `name_match="names"`. |
| `pattern` | `str \| None` | `None` | Regex pattern when `name_match="regex"`. |
| `declared_only` | `bool` | `False` | Restrict the search to methods declared on the target class itself, ignoring inherited methods. |
| `method_kind` | `str` | `"any"` | Method-kind filter: `"any"`, `"instance"`, `"classmethod"`, or `"staticmethod"`. |
| `min_count` | `int` | `1` | Minimum number of matching methods required. |
| `max_count` | `int \| None` | `None` | Maximum number of matching methods allowed (no upper bound when `None`). |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import require_method_set


class TestContract:
    __archtest__: Annotated[
        None,
        require_method_set(name_match="regex", pattern=r"test_.*", min_count=1),
    ]
```

## What it checks

- Cardinality of the selected method set on the matched target class.
- Selection by `name_match="any"`, `"regex"`, or `"names"`.
- Optional method-kind filter (`instance`, `classmethod`, `staticmethod`).
- Inheritance scope via `declared_only`.

## What it does not check

- Per-method signature shape — use `required_method(...)` for that.
- Attribute, property, or constructor presence — use `require_member_set(...)`.
- Public/private visibility semantics.

## See also

- [../api-reference.md](../api-reference.md) — full option surface and additional examples
- [require_member_set](require_member_set.md) — for non-method members or mixed kinds
