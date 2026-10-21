# `require_runtime_delegation`

Require the matched target function or method to delegate to an injected
collaborator — the runtime core of Strategy, Decorator, Proxy, and similar
patterns.

- **Category:** Runtime structure — design patterns
- **Placement:** function- or method-body `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import require_runtime_delegation
```

A `PriceCalculator` that receives a discount strategy and then applies a fixed
10 % itself has the right constructor and stores the strategy — and is not a
Strategy pattern. The case injects a **spy** with `{"$spy": "strategy"}`: a
recording stand-in that accepts any call. The rule requires the code to call
it.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `spy` (positional) | `str` | — | Name of the spy the code must delegate to. |
| `cases` | `list[dict]` | — | Call arguments; `{"$spy": spy}` must appear in them or in `init`. |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `member` | `str \| None` | `None` | Method that must be called on the spy (`"apply"`); `None` accepts any call, including calling the spy itself. |
| `init` | `dict \| None` | `None` | Methods only: constructor arguments, where a spy is usually injected. |
| `timeout_s` | `float` | `5.0` | Wall-clock limit per rule, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
class PriceCalculator:
    def __init__(self, strategy: Any) -> None:
        self.strategy = strategy

    def total(self, prices: list[float]) -> float:
        __archtest__: Annotated[
            None,
            require_runtime_delegation(
                "strategy",
                member="apply",
                init={"args": [{"$spy": "strategy"}]},
                cases=[{"args": [[10.0, 5.5]]}],
            ),
        ]
        return float(self.strategy.apply(sum(prices)))
```

A target computing `sum(prices) * 0.9` fails with `case 0: never delegated to
strategy.apply()`. Worked example:
[`example/rule_showcase/dyn008_patterns`](../../example/rule_showcase/dyn008_patterns/).

## The spy

- It is callable, and any public attribute is a method; every call is
  recorded with the spy's name, the member, and the argument count.
- A call returns its first positional argument (or `None`), so a pass-through
  chain keeps running. Code that needs a different return value may raise
  afterwards; the delegation has been recorded by then, and an exception is
  reported but not judged.
- Data attributes are not emulated: `strategy.rate * 2` gets a method, not a
  number.

## What it checks

- In every case, at least one call on the named spy (on `member`, if given).

## What it does not check

- What is passed to the collaborator or done with its result.
- Delegation to collaborators the code finds by itself rather than receives;
  combine with [forbid_runtime_instantiation](forbid_runtime_instantiation.md)
  to require that it receives them.

## Security

The target is executed; see [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [is_runtime_singleton](is_runtime_singleton.md), [enforce_runtime_observer](enforce_runtime_observer.md)
- [require_runtime_calls](require_runtime_calls.md) — delegation to a module rather than an object
