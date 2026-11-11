# `required_entity_signature`

Require a function or method to expose a compatible signature on the matched
target.

- **Category:** Signature & shape
- **Placement:** signature-level `Annotated[...]` (return annotation or parameter annotation), or function- or method-body `__archtest__: Annotated[...]`

## Usage

```python
from pythonarchtesting.rules import required_entity_signature
```

Place the marker inside an `Annotated[...]` on a parameter or return annotation
of the source function or method, or in its body as `__archtest__`. The
matched target callable must expose a compatible signature.

## Arguments

**Required:**

_None — the marker takes only optional arguments._

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `mode` | `str` | `"compatible"` | Signature matching mode: `"compatible"`, `"exact"`, or `"any"`. |
| `allow_extra_params` | `bool` | `True` | Accept target signatures with extra optional parameters (an extra required parameter always fails); `False` rejects every extra parameter. |
| `allow_param_rename` | `bool` | `False` | Pair parameters by position instead of by name, so a target may rename them (see [Compatible mode](#compatible-mode)). |
| `return_annotation` | `str` | `"warning"` | Return-type checking level: `"warning"`, `"error"`, `"off"`, or `"ignore"` (an alias of `"off"`). |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import required_entity_signature


def normalize(
    value: str,
) -> Annotated[
    str,
    required_entity_signature(mode="compatible", return_annotation="warning"),
]:
    return value.strip()
```

## What it checks

- Parameter shape on the matched target (arity, kind, defaults) under `mode="compatible"` or `mode="exact"`.
- Return-annotation presence or compatibility when `return_annotation` is enabled.

### Compatible mode

`mode="compatible"` asks whether the target can be called the way the
reference can. Each reference parameter is paired with a target parameter:
by name, or with `allow_param_rename=True` by position, the
positional-compatible and the keyword-only parameters separately. Both
pairings apply the same rules:

- a missing parameter fails (`missing parameter 'b'`; by position
  `target has fewer positional-compatible parameters than required`, or
  `… keyword-only parameters …`);
- a pair must agree in kind, an optional reference parameter must stay
  optional (`optional parameter became required`), and the target's
  annotation must accept the reference's;
- a target parameter left unpaired (by name: a name the reference lacks; by
  position: one beyond the reference's count of its group) is an extra
  parameter, judged by `allow_extra_params`.

The by-position messages name no parameter, since the two sides of a pair
may be named differently; the extra-parameter messages name the target's
parameters. The errors come pair by pair in the reference's order (by
position: positional pairs first), then one message about extra
parameters.

## What it does not check

- Async/sync parity: an `async def` reference is satisfied by a plain `def`
  target with the same parameters, and the reverse
  ([required_method](required_method.md) does compare it).
- Function or method body behavior — purely a signature check.
- Docstrings, decorators, or type-aliased return values beyond the configured `return_annotation` mode.
- Implementations attached to instance objects at runtime.

## See also

- [../api-reference.md](../api-reference.md) — full option surface
- [required_method](required_method.md) — same model for class methods
