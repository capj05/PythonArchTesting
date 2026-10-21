# Architectural mutants

An evaluation of how well the static and the runtime rules catch violations
of a program's architecture. Known violations are seeded into a correct
solution, one at a time, and each mutant is checked against the reference
with and without `--dynamic`.

```bash
python example/architectural_mutants/run.py            # all variants, writes results.md
python example/architectural_mutants/run.py --only M03,E06 --output /tmp/part.md
```

The results are in [results.md](results.md), which `run.py` regenerates.

## Setup

- `solution/` is a small layered order shop: `controller` → `service` →
  `repository`, with an `Order` model, discount strategies, an event bus,
  and a configuration singleton. Collaborators are injected, so the code is
  duck-typed (`service: Any`), as student solutions usually are.
- `reference/` is the same code plus markers for seven architectural intents.
  Where a static marker can express an intent, both kinds are declared:

  | Intent | Static marker | Runtime markers |
  |---|---|---|
  | I1 layering: the controller never touches storage | `forbid_imports` (reachable) | `require_runtime_calls`, `forbid_runtime_calls`, `enforce_reference_calls(require_all=True)` |
  | I2 dependency injection in the service | `forbid_imports` (direct) | `forbid_runtime_instantiation` |
  | I3 an `Order` changes only through its methods | — | `forbid_foreign_writes` |
  | I4 no `sqlite3`/`pickle` in the service | `forbid_imports` (direct) | `forbid_runtime_imports`, `forbid_runtime_calls` |
  | I5 the discount comes from the injected strategy | — | `require_runtime_delegation` |
  | I6 the event bus is an observer | — | `enforce_runtime_observer` |
  | I7 the configuration is a singleton | — | `is_runtime_singleton` |

- [`mutants.py`](mutants.py) holds 19 mutants in six operators (O1 layer
  bypass, O2 broken injection, O3 foreign write, O4 forbidden technology, O5
  skipped collaborator, O6 broken pattern) and six equivalent rewrites. Each
  mutant is an exact text replacement that breaks one intent.

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

## Findings

- Runtime rules caught 18 of 19 mutants. Static rules caught 4 of the 10
  mutants whose intent has a static marker at all (I1, I2, I4); the other 9
  break intents no static marker can state (I3, I5–I7) and are out of their
  reach by construction. No mutant was caught by static rules alone. The
  static rules caught only violations that need an `import` statement (M02,
  M05, M07, M11). Every mutant that works through an
  injected object (M01, M06), an attribute assignment (O3), a computed import
  (M12, M13), a missing call (O5), or a pattern's behaviour (O6) was caught
  at run time only. The computed imports of M12 and M13 happen inside
  `place()`, after the module has loaded, so `forbid_runtime_imports` (which
  watches the import itself) misses them and `forbid_runtime_calls` catches
  them when the module is used.
- M10 survives both: filling `order.items` in place is a mutation of a
  contained object, not an attribute assignment, which
  `forbid_foreign_writes` documents as out of reach.
- E06 is flagged by `enforce_reference_calls`: a new helper module adds an
  edge (`controller -> responses`) the reference does not have. This is what
  the marker promises — the reference's module graph, exactly — and the
  reason it is opt-in; the other markers accept the rewrite.
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
- Six equivalent rewrites are too few to estimate a false-positive rate;
  they only show that common refactorings are not flagged.
