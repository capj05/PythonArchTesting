# `forbid_private_access`

Require encapsulation in the matched target function or method: it may not
read an attribute starting with an underscore of an object other than its own.

- **Category:** Encapsulation
- **Placement:** function- or method-body `__archtest__: Annotated[...]`

## Usage

```python
from pythonarchtesting.rules import forbid_private_access
```

An attribute starting with an underscore is internal to its class. A function
that reads `inventory._stock` instead of calling `inventory.items()` depends on
how the class stores its data and breaks with every change inside it. The
check is static: it reads the target's code and runs nothing, so it needs no
cases and no `--dynamic`. Its runtime companion for writes is
[forbid_foreign_writes](forbid_foreign_writes.md).

## Arguments

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `allow` | `list[str] \| None` | `None` | Attribute names that may be read anyway (`["_cache"]`). |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

Any other argument, and any positional one, makes the declaration invalid
(`ENC001/forbid_private_access/invalid_declaration`): a misspelt `alow=[...]`
would otherwise silently allow nothing.

## Example

```python
from typing import Annotated
from pythonarchtesting.rules import forbid_private_access

from .inventory import Inventory


def report(inventory: Inventory) -> str:
    __archtest__: Annotated[None, forbid_private_access()]
    return "\n".join(f"{item}: {count}" for item, count in inventory.items().items())
```

A target whose `report` reads `inventory._stock.items()` fails with
`shop:report reads private attribute _stock of inventory (Inventory) at shop.py:<line>`.

## What it checks

- Every `obj._x` the body of the target reads, where `_x` starts with an
  underscore and is no dunder (a dunder such as `__init__` or `__class__` is
  no private attribute itself). A name-mangled `obj.__x`, and `obj._Owner__x`
  written out, count as private.
- A private attribute read by a constant name: `getattr(obj, "_x")`,
  `vars(obj)["_x"]` and `obj.__dict__["_x"]` count as `obj._x` (writing
  through `obj.__dict__["_x"] = v` does not).
- Code nested in the target counts: comprehensions, lambdas, local functions.
- Violations are reported in source order; of a chain (`obj._a._b`) the inner
  read comes first.
- Each violation has a fact in `details.facts`, aligned 1:1 with
  `details.violations`: `kind` (`read`), `attribute`, `class` (the class the
  annotation of the parameter read through names, else `null`), `file`,
  `line`, `reader` (`module:qualname`), and `receiver` (`true`, present
  only when the attribute is read to call a method on it that changes a
  container in place, `obj._x.append(v)` (`append`, `extend`, `insert`,
  `update`, `pop`, `popitem`, `remove`, `clear`, `setdefault`, `add`,
  `discard`, `sort`, `reverse`): a principle's findings count such a read on
  the line of a write of the same attribute as part of that write; so is a
  read in a statement that assigns that very attribute of the same object,
  `obj._x = {k: v for k, v in obj._x.items() if ...}`; `a._x = b._x.copy()`
  is a read of its own).

These are no violation:

- the method's own instance or class: its first parameter (`self`, `cls`,
  whatever it is called; not in a `@staticmethod`), `super()`, `type(self)`,
  `self.__class__`;
- in a method of the class that defines `_x`, or of a subclass of a project
  class that does (a class-level name, a method, or what its methods assign
  to their `self`, also by unpacking: `self._x, self._y = x, y`), any object:
  another instance of the same class (`other._x` in `__eq__`) is the class's
  own business. The check does not know `other`'s type, so in such a method
  an object of another class with an attribute of the same name passes too;
- `module._helper` on a name an import binds to a module (`import tools`,
  `from . import tools`): a module's private names are
  [module_interface](module_interface.md)'s concern, not an object's. A name
  the function binds itself (a parameter or a local named like the module,
  `def report(inventory): inventory._stock`) is the object, not the module;
- names that are public by convention: the API of a named tuple (`_replace`,
  `_asdict`, `_fields`, `_make`, `_field_defaults`) and sunder names such as
  an enum member's `_value_` and `_name_`;
- names listed in `allow`.

## What it does not check

- Writes: assigning or deleting the attribute or an item of it
  (`obj._x = v`, `obj._x[k] = v`, `obj._x[k] -= 1`, `del obj._x[k]`) are
  reported by [forbid_foreign_writes](forbid_foreign_writes.md), with what
  changed. A method call on it (`obj._x.append(v)`, `obj._x.get(k)`) reads it
  and counts here; when the call changes it, `forbid_foreign_writes` reports
  the change on the same line, and classifying the findings by a principle
  (`classify_target`) keeps that write only: one defect, one finding.
- Code outside the target's body: default values, decorators, and the
  module's top level, which runs at import time.
- Classes defined inside the target (their methods have their own `self`).
- Access by a name computed at run time: `getattr(obj, name)`.

## See also

- [forbid_foreign_writes](forbid_foreign_writes.md) — attribute writes from outside the object's class, at run time
- [module_interface](module_interface.md) — a module's private names used by other modules
