# `forbid_runtime_members`

Forbid given members on every instance of the matched target class, as
actually built — including members added dynamically.

- **Category:** Runtime structure
- **Placement:** class-body `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import forbid_runtime_members
```

The runtime counterpart of [`does_not_have`](does_not_have.md): a settings
object that does `self.__dict__.update(overrides)` stores a password nobody
wrote as `self.password = ...`. Building the instance shows it.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `*names` (positional) | `str` | — | Member names no instance may have. |
| `cases` | `list[dict]` | — | Constructor arguments (`args`, `kwargs`), see [Cases](../dynamic-checks.md#cases). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `timeout_s` | `float` | `5.0` | Wall-clock limit per rule, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
__archtest__: Annotated[
    None,
    forbid_runtime_members(
        "password",
        cases=[{"args": [{"port": 6543, "password": "s3cret"}]}],
    ),
]
```

A target that copies every override fails with `case 0: the instance has
'password' (from instance)`. Worked example:
[`example/rule_showcase/dyn005_runtime_members`](../../example/rule_showcase/dyn005_runtime_members/).

## What it checks

- Each name on the built instance, wherever it would be found (`__dict__`,
  class, bases, `__getattr__`).

## What it does not check

- Members added later by other method calls.
- Name patterns — list the names; see [does_not_have](does_not_have.md) for
  `pattern` and `aliases` in the static check.

## Security

The target is executed; see [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [require_runtime_members](require_runtime_members.md)
- [does_not_have](does_not_have.md) — the static check
