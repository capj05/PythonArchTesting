# Architectural mutants

An evaluation of how well the static and the runtime rules catch violations
of a program's architecture. Known violations are seeded into a correct
solution, one at a time, and each mutant is checked against the reference
with and without `--dynamic`, and by [import-linter](https://import-linter.readthedocs.io)
as a baseline.

```bash
pip install -e ".[eval]"                                # import-linter, the baseline tool
python example/architectural_mutants/run.py            # all variants, writes results.md and results.csv
python example/architectural_mutants/run.py --only M03,E06 --output /tmp/part.md --csv /tmp/part.csv
python example/architectural_mutants/run.py --program example/architectural_mutants_2
```

The results are in [results.md](results.md) and [results.csv](results.csv)
(one row per variant and tool), which `run.py` regenerates. A second program
in another architectural style, laid out the same way, is in
[`../architectural_mutants_2`](../architectural_mutants_2/).

## Setup

- `solution/` is a small layered order shop: `controller` → `service` →
  `repository`, with an `Order` model, discount strategies, an event bus,
  and a configuration singleton. Collaborators are injected, so the code is
  duck-typed (`service: Any`), as student solutions usually are.
- `reference/` is the same code plus markers for its architectural intents.
  Where a static marker can express an intent, both kinds are declared. The
  markers of the whole program (`enforce_layers`, `forbid_cycles`) are in the
  root `__init__.py`; their runtime part observes the controller handling an
  order and an empty order:

  | Intent | Static marker | Runtime markers |
  |---|---|---|
  | I1 layering: the controller never touches storage | `forbid_imports` (reachable), `enforce_layers` (`service` closed) | `require_runtime_calls`, `forbid_runtime_calls`, `enforce_reference_calls(require_all=True, allow_new_modules=True)`, `enforce_layers` |
  | I2 dependency injection in the service | `forbid_imports` (direct) | `forbid_runtime_instantiation` |
  | I3 an `Order` changes only through its methods | — | `forbid_foreign_writes` |
  | I4 no `sqlite3`/`pickle` in the service | `forbid_imports` (direct) | `forbid_runtime_imports`, `forbid_runtime_calls` |
  | I5 the discount comes from the injected strategy | — | `require_runtime_delegation` |
  | I6 the event bus is an observer | — | `enforce_runtime_observer` |
  | I7 the configuration is a singleton | — | `is_runtime_singleton` |
  | I8 no dependency cycles | `forbid_cycles` | `forbid_cycles`, `enforce_reference_calls` |
  | I9 modules are used through their public names | `module_interface` (on `models`) | `module_interface` |

- [`mutants.py`](mutants.py) holds 22 mutants in eight operators (O1 layer
  bypass, O2 broken injection, O3 foreign write, O4 forbidden technology, O5
  skipped collaborator, O6 broken pattern, O7 dependency cycle, O8 module
  interface) and ten equivalent rewrites. Each mutant is an exact text
  replacement, where needed with a new, renamed or removed module, that breaks
  one intent. I9 has no marker yet: its mutant (M22) measures the state
  before one exists.
- [`baselines/importlinter.py`](baselines/importlinter.py) turns the
  reference's import markers into import-linter contracts, so the baseline
  checks the same intents: `forbid_imports` into `forbidden` (`mode="direct"`
  maps to `allow_indirect_imports = True`), `enforce_layers` into `layers`
  (without `closed`, which import-linter's configuration cannot state),
  `forbid_cycles` into `acyclic_siblings`.

## Counting

A mutant is caught when a marker of the intent it breaks (its `detected_by`)
fails with a violation; a failure of an unrelated marker, or a runtime rule
that could not run (`probe_*`, `case_setup_failed`), does not count. This
follows the kill criterion of property-based mutation testing: a mutant is
killed only by a violation of the property it breaks (E. Bartocci, L.
Mariani, D. Ničković, D. Yadav: *Property-Based Mutation Testing*, ICST 2023,
doi:10.1109/ICST57152.2023.00029). The mutants here change the program's
structure, not its computations, and are used to evaluate the checker, not
the target's tests.
"Static" counts the static rules of a run without `--dynamic`; "Runtime"
counts the runtime rules of a run with it. An equivalent rewrite on which any
rule fails is a false positive.

## Model mode

The `Model` column runs the CLI with `--dynamic` against a different
reference: `solution/` plus [`model/__init__.py`](model/__init__.py), which
declares nothing but `architecture_entry` (the entry and the cases of the
root markers). The reference itself is the model: a module dependency it does
not have is a violation, in imports, calls between modules, objects created
and libraries used. A mutant counts as caught when either `architecture_entry`
rule fails with a violation; an equivalent rewrite on which one fails is a
false positive.

## Findings

- The model mode, with one declaration (`require_all=True`) and no other
  marker, caught 15 of the 22 mutants: every layer bypass (M01–M04, M20),
  every broken injection (M05–M07), every forbidden technology (M11–M13),
  every skipped collaborator (M14–M16) and the cycle (M21). M04 and M14–M16
  make fewer calls, not other ones; `require_all` turns the reference's call
  that never happened into a violation. Foreign writes and broken patterns
  (I3, I6, I7) stay with their markers, as intended. False
  positives: E08 (three modules in one: its static part, whose imports now
  join one module) and E10 (a function turned into a static method, which the
  matching cannot pair: `required_target_missing` for the markers too); the
  renamed module (E07), on which import-linter stops with an error, passes.
- Runtime rules caught all 22 mutants; M22, which breaks I9, is caught
  since `module_interface` states it, statically too. Static rules caught 6 of the 13
  mutants whose intent has a static marker at all (I1, I2, I4, I8, I9); the
  others break intents no static marker can state (I3, I5–I7) and are out
  of their reach by construction. No mutant was caught by static rules alone.
  import-linter, given the same import intents as contracts, caught 5 of
  them (it has no contract for a module's interface, so not M22). The static rules caught
  only violations that need an `import` statement (M02, M05, M07, M11, M21).
  Every mutant that works through an injected object (M01, M06), an
  attribute assignment or a change to what an attribute holds (O3), a
  computed import (M12, M13), a missing call (O5), or a pattern's behaviour
  (O6) was caught at run time only. The computed imports of M12 and M13
  happen inside `place()`, after the module has loaded, so
  `forbid_runtime_imports` (which watches the import itself) misses them and
  `forbid_runtime_calls` catches them when the module is used.
- `enforce_layers`, one declaration for the whole program, caught every
  layer bypass the per-module markers caught except M04 (the controller
  computes the total itself, which is a missing call, not a call into a
  wrong layer). At run time it catches the bypasses that need no import
  (M01, M03, M20) as calls past the closed `service`: a call the reference
  does not make, from the controller into a layer below the service. A call
  "upwards" that the reference makes as well (a callback, an injected
  object) is not a violation, so the rule does not flag the design itself.
- M10 fills `order.items` in place: no attribute is assigned, the list it
  holds changes. It survived every rule until `forbid_foreign_writes` began
  comparing what an object's attributes hold, not only watching their
  assignment; it is now caught as `service:place changes what is held in
  Order.items`.
- E06, a new helper module of the target's own, was flagged by
  `enforce_reference_calls` while the reference demanded its module graph
  exactly (`controller -> responses` is no edge of the reference). With
  `allow_new_modules=True` the helper counts as part of the controller and
  E06 passes, while M20, the same kind of helper used to reach storage, is
  still a divergence (`controller -> repository`). `forbid_runtime_calls`
  misses M20: by default it counts only the calls the controller's own code
  makes, and `transitive=True`, which the reference does not set, would count
  the helper's call too. The runtime `enforce_layers` folds the helper into
  the controller the same way and catches M20.
- M21, a dependency cycle between `models` and `service`, is caught
  statically by `forbid_cycles` (and by `enforce_layers`, since `models` is
  below `service`), at run time by `forbid_cycles`, as a cycle of calls the
  reference does not have, and by `enforce_reference_calls`, as a new edge
  `models -> service`. import-linter's `acyclic_siblings` catches it too. M22,
  a private helper of `models` used by the service, passes everything.
- Two equivalent rewrites fail because the matching finds no counterpart for
  a reference entity, not because a rule sees a violation. In E08 (controller,
  service and repository in one module) the classes and functions are paired
  by name since `[matching] name_fallback`
  ([matching_weights](../matching_weights/README.md)); only
  `forbid_runtime_imports`, declared on a merged module, still has no
  target (before, every runtime rule of those modules failed with
  `required_target_missing`). In E10 (the controller function
  turned into a `staticmethod`) the controller's runtime rules do, among them
  the runtime parts of `enforce_layers` and `forbid_cycles`, which observe
  the controller. Their static parts pass both: they judge the whole import
  graph, with target modules named by the reference modules they were
  matched to. The static `forbid_imports` markers skip an unmatched module
  instead (`fail_on_unmatched=False`), so the static run reports nothing.
  This is the matching risk of a solution that structures its code
  differently from the reference; the results table names these markers in
  a column of their own.
- import-linter has no matching: its contracts name the reference's modules.
  Its `layers` contract requires every layer to exist, so it reports an error
  on E07 (the repository renamed to `storage`) and on E08 (`Module
  'solution.controller' does not exist`), where `enforce_layers` translates
  the names and passes.
- Two corrections came out of the first run and are kept in the setup:
  - The first reference gave the controller only a non-empty order. M03, a
    bypass on the empty-order path, then passed every rule, and the passing
    results named the line no case ran (`no case ran lines 10 ... of
    controller.py`). An empty-order case added to `forbid_runtime_calls` and
    `enforce_reference_calls` catches it.
  - With the default `mode="reachable"`, `forbid_imports` missed M07's import
    inside `place()`: the reachable graph only follows imports made when a
    module is imported. The service's marker uses `mode="direct"`, which reads
    every import statement, and the limit is now documented in
    [forbid_imports](../../docs/markers/forbid_imports.md).

## Limits of this evaluation

- One small program and hand-seeded mutants: the numbers show which kinds of
  violation each kind of rule can see, not detection rates to expect on real
  submissions.
- The seeded violations are of the kinds the markers were designed for; a
  violation of an intent no marker states is caught by neither kind.
- The same author wrote the solution, the reference with its markers and
  cases, and the mutants, so the mutants may favour what the markers check.
- The reference was adjusted after the first run (the empty-order case and
  `mode="direct"`, see Findings) and then evaluated on the same mutants: the
  final numbers are not from a held-out set.
- Ten equivalent rewrites are too few to estimate a false-positive rate;
  they show which kinds of refactoring are flagged and why.
