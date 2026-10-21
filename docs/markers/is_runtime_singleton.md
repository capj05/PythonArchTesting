# `is_runtime_singleton`

Require the matched target class to hand out one shared instance (Singleton).

- **Category:** Runtime structure — design patterns
- **Placement:** class-body `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import is_runtime_singleton
```

A Singleton can be written with a class attribute and a `classmethod`, with
`__new__`, with a metaclass, or with a module-level cache — no static rule
recognises all of them. What they share is observable: asking twice gives the
same object.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `cases` | `list[dict]` | — | Arguments for each access (`args`, `kwargs`), see [Cases](../dynamic-checks.md#cases). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `access` | `str \| None` | `None` | Name of the class-level accessor (`"instance"` for `Config.instance()`); `None` calls the class itself. |
| `timeout_s` | `float` | `5.0` | Wall-clock limit per rule, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
class AppConfig:
    __archtest__: Annotated[
        None, is_runtime_singleton(access="instance", cases=[{"args": []}])
    ]
    _instance = None

    @classmethod
    def instance(cls) -> "AppConfig":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
```

A target whose `instance()` returns `cls()` fails with `case 0: two accesses
via instance returned different objects`. Worked example:
[`example/rule_showcase/dyn008_patterns`](../../example/rule_showcase/dyn008_patterns/).

## What it checks

- Per case, two consecutive accesses return the identical object (`is`).

## What it does not check

- That direct construction is prevented when an accessor exists — Python
  cannot make a constructor private; `Config()` may still build a second one.
- Thread safety of the lazy initialisation.

## Security

The target is executed; see [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [enforce_runtime_observer](enforce_runtime_observer.md), [require_runtime_delegation](require_runtime_delegation.md)
