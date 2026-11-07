# `forbid_runtime_calls`

Forbid the matched target function or method's module from calling directly
into given modules while it runs — a layering rule checked on the calls that
actually happen.

- **Category:** Runtime structure
- **Placement:** function- or method-body `__archtest__: Annotated[...]`
- **Runs only with:** `python-arch-test --dynamic`; without the flag the rule is
  `SKIPPED` and does not affect the exit code.

## Usage

```python
from pythonarchtesting.rules import forbid_runtime_calls
```

A controller that receives its service as a parameter has no import of the
repository, yet `service.repository.get(...)` reaches straight into the storage
layer. [`forbid_imports`](forbid_imports.md) cannot see that, because the
dependency travels through an object whose type the source does not state
(dependency injection, duck typing, `getattr`). This marker calls the target
with the declared cases and records every call that **code of the target's
module** makes into another module.

## Arguments

**Required:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `*modules` (positional) | `str` | — | Dotted module names the code must not call; each also covers its submodules. |
| `cases` | `list[dict]` | — | Call arguments that drive the code, see [Cases](../dynamic-checks.md#cases). |

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `allow` | `list[str] \| None` | `None` | Modules exempt from `modules`, e.g. `["repository.queries"]` under a forbidden `"repository"`. |
| `transitive` | `bool` | `False` | Also count calls that other project code makes while the target runs, so a detour through a helper module is caught ([Detours](#detours-transitivetrue)). |
| `through` | `list[str] \| None` | `None` | With `transitive=True`: modules whose code may make the call on the target's behalf — the layer in between, e.g. `["service"]`. |
| `init` | `dict \| None` | `None` | Methods only: constructor arguments for every case, `{"args": [...], "kwargs": {...}}`. |
| `timeout_s` | `float` | `5.0` | Wall-clock limit per rule, in `(0, 60]`. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

Module names are those of the reference, without the package the root is
imported as (`"repository"`, not `"target_7.repository"`), or any other
importable module (`"sqlite3"`). A target that keeps a layer in a module of
another name, or several layers in one module, is judged by the matched
entities: a call into the target's `storage.OrderRepository.get` is a call
into `repository` when that class was matched to the reference's
`repository.OrderRepository`. Only code of the rule's own layer counts as the
caller, so the service's calls do not count against the controller when both
live in one target module.

A dotted name may also name one function of a module. File and console I/O
go through builtins, which are otherwise not recorded: `"io"` forbids
`open()` (it is `io.open`) together with the file objects' methods, and
`"builtins.print"` and `"builtins.input"` forbid console output and input —
for a domain layer that must not do I/O.

## Example

```python
from typing import Annotated, Any
from pythonarchtesting.rules import forbid_runtime_calls


def handle_order(request: dict[str, Any], service: Any) -> dict[str, Any]:
    __archtest__: Annotated[
        None,
        forbid_runtime_calls(
            "repository",
            cases=[{"args": [
                {"id": "A1", "prices": [10.0, 5.5]},
                {"$new": "service.OrderService",
                 "args": [{"$new": "repository.OrderRepository"}]},
            ]}],
        ),
    ]
    total = service.place(request["id"], request["prices"])
    return {"status": "ok", "total": total}
```

A target whose controller calls `service.repository.get(...)` fails with
`case 0: handle_order calls repository:OrderRepository.get (line 17)`.
Worked example:
[`example/rule_showcase/dyn001_layers`](../../example/rule_showcase/dyn001_layers/).

### Detours (`transitive=True`)

By default only the target module's own calls count: a controller that calls
`helpers.load()`, which calls the repository, passes, because the call into
`repository` is the helper module's. With `transitive=True` every call made
by project code while code of the target's module is further up the stack
counts as well, and the violation names the chain:

```python
forbid_runtime_calls(
    "repository", transitive=True, through=["service"], cases=[...],
)
```

```text
case 0: controller:handle -> helpers:load calls repository:OrderRepository.get (line 6 of helpers)
```

That alone would forbid the service from using the repository on the
controller's behalf too; `through=["service"]` names the layer in between, so
a chain that passes through code of `service` is the layering working as
intended. Library code on the way is skipped, and modules are judged by the
matched entities, as for `modules`.

## What it checks

- Direct calls from any code of the target's module — the entity itself and
  every helper of the same module it runs — into a function, method, or
  constructor of a forbidden module.
- Calls of C functions and methods of C types too: `pickle.dumps` (implemented
  in `_pickle`) is reported as `pickle`, `cursor.execute` as `sqlite3`.
- Calls made through objects passed in, attributes, `getattr`, or names
  computed at run time — whatever actually executes.

## What it does not check

- Indirect calls, unless `transitive=True`: when the target calls the service
  and the service calls the repository, only the first call belongs to the
  target's module. That is the layering the rule expresses.
- With `transitive=True`, calls whose stack does not contain the target's
  code: calls in threads the target starts, and callbacks it registered that
  run after it returned.
- Calls of builtins (`len`, `list.append`) — they belong to no layer. The I/O
  builtins `open`, `print`, and `input` are the exception (see above).
  `isinstance()` and `type()` are recorded only when the rule names them
  (`builtins.isinstance`, `builtins.type`; plain `builtins` does not), so
  that code branching on the type of an object can be forbidden without
  every other rule's report growing with them. `type()` is seen from
  Python 3.12 on (through `sys.monitoring`, tool id 3 or 4 first, the
  debugger's 0 last); before that, or with no tool id free, it is not
  recorded, and the result says so: `details.unobserved_calls` names the
  call and why, a pass carries `calls_not_observable` in
  `details.unverified` and its message ends in `not observable: ...`.
  Each call site is recorded once per case.
- A call of `isinstance()` or `type()` that plainly tests no type of an
  object. The rule reads the line of each such call in the target's code and
  drops only two kinds: `isinstance(x, C)` when every class it names is a
  builtin or standard library type (`int`, `float`, `str`, `bool`, `list`,
  `dict`, `set`, `tuple`, `bytes`, `complex`, `type(None)`, a builtin
  exception, `numbers.Number` and the other `numbers` classes,
  `collections.abc` classes such as `Mapping`, `decimal.Decimal`, ...; also
  imported under another name), and `type(x)` that is only displayed: a
  value of an f-string, an argument of `print`, `str`, `repr` or `format`,
  or its `__name__` / `__qualname__` in an f-string or a concatenation,
  where what displays it is not compared, used as a subscript key, a
  `match` subject or the key of `.get()`. So `if not isinstance(items,
  list): raise ...`, `isinstance(a, (int, float))` and
  `f"{type(x).__name__}"` are no violations. Every other call counts: a
  project class, also imported under another name (`isinstance(x, C)` after
  `from .shapes import Circle as C`), a tuple of classes kept in a constant
  (`isinstance(x, SHAPES)`), a class held by an attribute
  (`isinstance(x, self.kind)`) or computed at run time, `type(x)` kept in a
  variable (`t = type(x)`), compared, or used as a key
  (`handlers.get(type(x))`), and a file or line the rule cannot parse.
  Several calls on one line count when any of them does.
- Calls the cases do not reach; see [Cases](../dynamic-checks.md#cases).
- What the call computes. Results are never compared.

## Security

The target is executed; see [Dynamic checks § Security](../dynamic-checks.md#security).

## See also

- [require_runtime_calls](require_runtime_calls.md) — the positive counterpart:
  the code must go through a layer
- [forbid_imports](forbid_imports.md) — the static policy on import statements
- [forbid_runtime_imports](forbid_runtime_imports.md) — imports performed while
  the module loads
