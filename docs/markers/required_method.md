# `required_method`

Require a class to expose a method with a compatible signature.

- **Category:** Signature & shape
- **Placement:** method-body `__archtest__: Annotated[...]`
## Usage

```python
from pythonarchtesting.rules import required_method
```

Place inside the body of the source method that defines the contract. The
matched target class must expose a method that satisfies the configured name
and signature constraints.

## Arguments

**Required:**

_None — the marker takes only optional arguments._

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `signature_mode` | `str` | `"compatible"` | Signature matching mode: `"compatible"`, `"exact"`, or `"any"`. |
| `enforce_method_kind` | `bool` | `True` | Require method-kind parity (instance / classmethod / staticmethod) between source and target. |
| `allow_missing` | `bool` | `False` | Pass when no candidate method exists on the target instead of failing. |
| `declared_only` | `bool` | `False` | Restrict the search to methods declared on the target class itself, ignoring inherited methods. |
| `name_match` | `str` | `"exact"` | Name selector: `"exact"`, `"aliases"`, `"regex"`, or `"any"`. |
| `aliases` | `list[str] \| None` | `None` | Accepted alternative names when `name_match="aliases"`. |
| `pattern` | `str \| None` | `None` | Regex pattern when `name_match="regex"`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import required_method


class Calculator:
    def add(self, a: int, b: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(
                signature_mode="compatible",
                declared_only=True,
            ),
        ]
        return a + b
```

## What it checks

- Presence of a method with a matching name (or alias / regex / any) on the matched target class.
- Parameter compatibility under the configured `signature_mode`.
- Method-kind parity (instance / classmethod / staticmethod) when `enforce_method_kind=True`.
- Async/sync parity in all modes.

## What it does not check

- Method body, return value semantics, or exceptions raised.
- Visibility (public/private) or name-mangling.
- Decorator stacks beyond the configured method-kind check.

## See also

- [../api-reference.md](../api-reference.md) — full option surface, including alias/regex/any examples
- [require_method_set](require_method_set.md) — for set-cardinality checks across many methods
