# `implements_runtime_protocol`

Require instances of the matched target class, as actually built, to provide
every member of a `typing.Protocol`, with methods callable as the protocol
declares.

- **Category:** Runtime structure
- **Placement:** class-body `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import implements_runtime_protocol
```

[`implements_protocol`](implements_protocol.md) compares the class body with
the protocol. A class whose `export` is bound in `__init__`
(`self.export = self._to_csv`), inherited from a library, or added by a
decorator conforms at run time but not on paper. This marker builds an
instance and checks the protocol's members on it.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `protocol` (positional) | Protocol class | — | A `typing.Protocol` defined in the reference. |
| `cases` | `list[dict]` | — | Constructor arguments (`args`, `kwargs`), see [Cases](../dynamic-checks.md#cases). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `timeout_s` | `float` | `5.0` | Wall-clock limit per rule, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated, Protocol
from pythonarchtesting.rules import implements_runtime_protocol


class Exporter(Protocol):
    name: str

    def export(self, rows: list[dict[str, str]]) -> str: ...


class CsvExporter:
    __archtest__: Annotated[
        None,
        implements_runtime_protocol(Exporter, cases=[{"args": [";"]}]),
    ]
    ...
```

A target whose `export` takes no rows fails with `case 0: 'export' does not
accept 1 positional argument(s)`. Worked example:
[`example/rule_showcase/dyn006_runtime_classes`](../../example/rule_showcase/dyn006_runtime_classes/).

## What it checks

- Every protocol attribute exists on the instance.
- Every protocol method exists, is callable, and its signature accepts the
  protocol's required positional arguments (`inspect.signature(...).bind`).

## What it does not check

- Annotations and return types — the static
  [implements_protocol](implements_protocol.md) compares those.
- Keyword-only parameters and defaults beyond the positional count.
- What the methods return.

`--validate-declarations` reports the protocol argument as a non-literal
warning, as it does for `implements_protocol`; the protocol is resolved by
name from the reference.

## Security

The target is executed; see [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [implements_protocol](implements_protocol.md) — the static check
- [require_runtime_members](require_runtime_members.md) — members by name
