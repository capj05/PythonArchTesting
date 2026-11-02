# `architecture_entry`

Compare the target with the reference's module dependencies: the reference
itself is the model of the architecture, and no per-module markers are needed.

- **Category:** Imports
- **Placement:** the reference's root `__init__.py`, module-level
  `__archtest__: Annotated[...]`
- **Runs:** the static check always; the runtime check (with `entry` and
  `cases`) only with `python-arch-test --dynamic`, otherwise it is `SKIPPED`.
  `python-arch-test --architecture` adds the static check to a reference that
  does not declare the marker.

## Usage

```python
from pythonarchtesting.rules import architecture_entry
```

Where [`enforce_layers`](enforce_layers.md) states an architecture, this
marker reads it off the model solution: every module dependency the
reference has is allowed, every other one is a violation. The declaration
only says which function to run, and on which cases, to see what the
reference does at run time.

## Arguments

**Optional:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `entry` | `str \| None` | `None` | A reference function or method, `"module.function"` or `"module.Class.method"`, that the runtime check runs. |
| `cases` | `list[dict] \| None` | `None` | Calls of `entry`, in the [case language](../dynamic-checks.md#cases). Required together with `entry`. |
| `init` | `dict \| None` | `None` | Constructor arguments when `entry` is a method. |
| `policy` | `str` | `"allow_new_modules"` | How strictly to compare. `"allow_new_modules"`: a module the reference does not have (a helper of the target's own) counts as part of the modules that use it. `"strict"`: every dependency the reference lacks is a violation. `"layered"`: an extra dependency is a violation only when it points against the reference's direction (the reference reaches its origin from its end); any other is undecided. |
| `allow` | `list[str] \| None` | `None` | Exceptions that are never a violation, as `"module -> module"` or `"module -> package"` (a library). A package covers its submodules (`"pkg -> models"` covers `pkg.a -> models`). |
| `forbid` | `list[str] \| None` | `None` | Dependencies that are always a violation, even when the reference has them or the library is in `ignore_external`. |
| `ignore_external` | `list[str] \| None` | `None` | Libraries never judged. A list replaces the default, it does not extend it. `None` means language support: `__future__`, `typing`, `typing_extensions`, `abc`, `dataclasses`, `enum`, `functools`, `itertools`, `collections`, `contextlib`, `types`, `operator`. |
| `require_all` | `bool` | `False` | At run time, a call between modules the reference makes and the target does not (a step the target skips) is a violation too, not only reported as absent. The static check is not affected: a missing import says little. Needs `entry`. |
| `ignore_type_checking` | `bool` | `True` | Leave out imports inside `if TYPE_CHECKING:`. |
| `timeout_s` | `float` | `5.0` | Time limit per run of the cases. |
| `severity` | `str` | `"error"` | Violation severity (`"error"`, `"warning"`, `"info"`). |
| `message` | `str` | `None` | Custom violation message override. |

## Example

```python
# reference/__init__.py
from typing import Annotated

from pythonarchtesting.rules import architecture_entry

__archtest__: Annotated[
    None,
    architecture_entry(
        entry="controller.handle_order",
        cases=[{"args": [{"id": "A1", "prices": [10.0]},
                         {"$new": "service.OrderService",
                          "args": [{"$new": "repository.OrderRepository"},
                                   {"$new": "pricing.NoDiscount"},
                                   {"$new": "events.EventBus"}]}]}],
    ),
]
```

## What it checks

The model has layers, and each is compared edge by edge in reflexion-model
terms: an edge both have *converges*, one only the target has *diverges* (a
violation), one only the reference has is *absent* (reported, not a
violation, except for runtime calls with `require_all=True`). All of it is in `details.architecture` of the result. The Markdown report shows it per target in an
**Architecture** section: a count table per layer of each rule, then the
divergent, undecided, absent and allowed edges; passes with undecided
changes are counted in the target's and the run's summary. The section
also has, derived from the same comparison and judging nothing again:

- a **dependency matrix** per module layer (`imports`, `calls`,
  `instances`; an object counts for its class's module, also for a nested
  class): a row uses a column, `=` convergent, `+` divergent, `-` absent,
  `?` undecided, `a` allowed. Where several objects share a cell, the kind
  most in need of a reader wins (`+`, then `?`, `-`, `a`, `=`). A layer of
  more than 15 modules gets one line instead;
- **module metrics**, fan-in, fan-out and instability (fan-out / (fan-in +
  fan-out)) per module, reference against target, over the rule's module
  layers. The reference side counts every reference edge, including one an
  exception or `forbid` covers (each layer's `reference` list). They are informative only and never part of the verdict:
  coupling numbers do not tell whether the intended structure holds;
- **static vs runtime**, with both rules: the target's module edges only
  imported (a dead import, an import for annotations, or one no case
  exercised) and only seen at run time (an injected object, a computed
  import, a callback), each marked when the reference shows it the same
  way. Both sides are named and folded as in the comparison.

With several targets, the run's `report.md` has **Architecture Across
Targets**: the divergent, absent and undecided edges at least two targets
share, most shared first (20 at most). A divergent or absent edge at
least 90 % of three or more targets share is marked "check the model": the
reference may lack an edge the assignment allows (or require one it need
not), rather than every solution being wrong. An undecided edge is never
marked: the policy leaves it open on purpose. The JSON report is unchanged; all of it is derived from
`details.architecture`.

- **Static (`DEP004`)**, on every import statement of the target:
  - `imports`: module-to-module imports. `from .pkg import Name` depends on
    the module `pkg/__init__.py` takes `Name` from, not on the package. A
    subpackage's `__init__.py` importing its own submodules (a re-export)
    is organisation inside a layer and is listed as allowed; the root
    package's `__init__.py` importing a module stays a divergence: the root
    is the assignment's public face. Importing a subpackage whole (`from . import api`, then
    `api.book()`) converges when the reference imports one of its modules
    from the same module.
  - `external`: the libraries imported. A library the reference imports
    anywhere may be imported by any module; moving `json` from one module to
    another is not a change of technology. Under `allow_new_modules` and
    `layered` a library a new helper module imports counts for the modules
    using it, so `forbid=["controller -> sqlite3"]` also catches `sqlite3`
    moved into a helper the controller imports. A library the reference
    never uses diverges, harmless or not: list the ones a solution may
    bring in (`json` for a store that serialises) in `ignore_external`,
    together with the default ones it replaces.
  - An absolute import through the target's directory name or the
    reference's package name is an import inside the project, not a library.
- **Runtime (`DYN011`)**, with `entry`, `cases` and `--dynamic`, across all
  cases at once:
  - `calls`: the calls between modules. A call along an import the
    reference has converges even when the reference's cases never make it:
    the import says the dependency is intended. It never counts as absent.
  - `instances`: which module creates objects of which class (a service that
    builds its own repository instead of taking it as an argument);
  - `external`: the libraries called, including through `importlib`.
- Target modules and classes are named by the reference entities they were
  matched to, so a renamed module still stands for its original.
- A change the policy cannot decide passes: the result is `OK`, the change is
  listed in `details.undecided`, the summary says how many there are, and the
  CLI and the MCP `summarize_report` count them. Undecided are the edges of a
  new module no known module uses, the extra edges `layered` tolerates, and
  objects of a target class that matches nothing in the reference.

## What it does not check

- Attribute writes and the order of calls inside one module; markers such as
  [`forbid_foreign_writes`](forbid_foreign_writes.md) and
  [`enforce_runtime_observer`](enforce_runtime_observer.md) cover those.
- Calls that no case drives; the coverage note of a pass lists the lines of
  the entry's module that did not run.
- A target whose entities cannot be matched to the reference's (modules
  merged or split beyond recognition): its modules keep their own names and
  are judged as new modules; an assisted-pairing mapping (`--mapping`) pairs
  them.
- Libraries used only through code they generate themselves (an `attrs`
  constructor defined in the library): such code has no file and is not
  counted as library use.
- `--architecture` on a reference that is not a package (no root
  `__init__.py`): there is no root module to attach the rule to, so it only
  logs a warning and adds nothing.

## The model as data

`python-arch-test --source REFERENCE --write-model model.json` writes the
model this marker compares with: the modules, the imports between them
(with the line of each), the libraries each module imports, the
declaration and when a target is compared at all (`compared`); with
`--dynamic` also what the declared cases do (calls, objects created,
libraries called, and the libraries a target may call at run time: those
plus every library the reference imports). A case of the reference that
does not run makes the status `reference_failed`: the comparison would end
in `ERROR`. `--write-model` takes only the reference's flags (`--source` or
a configured `[projects].source_path`, `--reference-modules`, `--config`,
`--dynamic` with its sandbox) and warns when the declaration does not
compile or the cases did not run. The MCP tool `describe_architecture`
returns the same. It describes the reference and judges nothing; the
comparison always reads the reference itself, not this file.

## See also

- [enforce_layers](enforce_layers.md) — a layer order stated by hand
- [enforce_reference_calls](enforce_reference_calls.md) — the reference's calls from one function
- [../dynamic-checks.md](../dynamic-checks.md) — how runtime checks run
