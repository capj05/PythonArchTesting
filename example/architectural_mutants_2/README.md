# Architectural mutants: ports and adapters

The second program of the [architectural-mutant evaluation](../architectural_mutants/README.md),
in another architectural style, so that its findings do not rest on one
program. The setup, the counting and the harness are the same; only the
program, its intents and its variants differ.

```bash
python example/architectural_mutants/run.py --program example/architectural_mutants_2
```

The results are in [results.md](results.md) and [results.csv](results.csv).

## Setup

- `solution/` lends library books in ports-and-adapters (hexagonal) style:
  a `domain` (`Loan`), `ports` (`LoanStore`, `Notifier`, `Clock` as
  `Protocol`s), the `application` core (`LendingService`, written against the
  ports), driven adapters (`adapters_memory`, `adapters_notify`), a driving
  adapter (`api`, request handlers) and a composition root (`wiring`), the
  only module that names the concrete adapters.
- `reference/` is the same code plus markers for eight intents. The two of
  the whole program (H7, H8) are declared once, in the root `__init__.py`;
  their runtime part observes a handler lending a book and rejecting an
  incomplete request:

  | Intent | Static markers | Runtime markers |
  |---|---|---|
  | H1 the domain depends on nothing else in the project | `forbid_imports` (direct) | through `enforce_reference_calls` of the handlers |
  | H2 the application uses ports, not adapters | `forbid_imports` (direct) | `forbid_runtime_instantiation` |
  | H3 each adapter satisfies its port | `implements_protocol` | `implements_runtime_protocol` |
  | H4 the handlers talk to the application only | `forbid_imports` (reachable) | `require_runtime_calls`, `forbid_runtime_calls(transitive=True, through=["application"])`, `enforce_reference_calls(require_all=True, allow_new_modules=True)` |
  | H5 a loan is closed only through `Loan.close` | — | `forbid_foreign_writes` |
  | H6 lending notifies through the injected notifier | — | `require_runtime_delegation` |
  | H7 one layer order: `wiring`, then `api \| adapters_memory \| adapters_notify` (independent), `application`, `ports`, `domain` | `enforce_layers` | `enforce_layers` |
  | H8 no dependency cycles | `forbid_cycles` | `forbid_cycles` |

  Unlike the first program, `forbid_runtime_calls` counts detours
  (`transitive=True`), so a handler that reaches an adapter through a helper
  module of its own is a violation of it too.
- [`mutants.py`](mutants.py) holds 13 mutants (O1 layer bypass, O2 broken
  injection, O3 foreign write, O5 skipped collaborator, O7 dependency cycle,
  O9 broken port, O10 dependent domain) and six equivalent rewrites. The
  layer order H7 restates H1, H2 and H4, so the mutants of those intents
  count `enforce_layers` among their markers.

## Findings

- The model mode (see the first program's README; here
  [`model/__init__.py`](model/__init__.py) runs `api.lend_book` with
  `require_all=True`) caught 10 of the 13 mutants: all of layering,
  injection, the dependent domain and the cycle (M01–M07, M12, M13) and the
  skipped notification (M09), with no false positive on any equivalent
  rewrite. The renamed and the merged adapter modules (E02, E03), on which the
  per-module markers find no target, pass. The broken ports (M10, M11) and
  the foreign write (M08) stay with their markers.
- E06 (the loan as a dataclass) no longer fails `enforce_reference_calls`:
  the probe now counts the `__init__` that `dataclasses` generates as code of
  the class's module, so the reference's `application -> domain` call is seen
  on the target too.
- Runtime rules caught all 13 mutants, static rules 8, import-linter 6. The
  static rules caught every mutant that needs an `import` statement (M02,
  M04–M06, M12, M13) and the two broken ports, M10 (the adapter no longer has
  the method its port demands) and M11 (`implements_protocol`); those two are
  the difference from import-linter, which checks imports only. No mutant was caught by static
  rules alone.
- M11 gives `find` a second required parameter. `implements_runtime_protocol`
  catches it by calling the method as the port does; since 2026-11-01 the
  static `implements_protocol` does too (under `signature_mode="compatible"`
  an extra parameter must be optional; before, any extra parameter passed).
- M03, a detour through a helper module of the handler's own, is caught both by
  `enforce_reference_calls` (the helper folds into `api`, so the edge
  `api -> adapters_memory` is a divergence) and by `forbid_runtime_calls`,
  which here counts detours (`transitive=True`). In the first program, where
  that option is not set, `forbid_runtime_calls` misses the same kind of
  mutant (M20).
- M13 closes a cycle `application -> domain -> application` through an import
  inside `Loan.close()`. The static `forbid_cycles` names the cycle, as it
  reads imports inside functions too; it is also a violation of H1 and of the
  layer order (the domain imports the application). Placed at module level,
  the same import makes the program fail with an `ImportError` whenever the
  domain is imported first, so the mutant imports inside the method.
- `enforce_layers` caught the layer bypasses that need no import (M01, M03)
  at run time: the handler calls into `adapters_memory`, its independent
  sibling, and the reference does not. The application calls the driven
  adapters at run time as well, "upwards" in the layer order, but through
  the ports it was given, as the reference does; those calls are not
  violations. It does not catch M04 (a handler builds a `Loan`): the domain
  lies below the handlers, and no layer between them is closed, since the
  driven adapters use the domain directly.
- No equivalent rewrite fails. Two failed before pairing by name
  (`[matching] name_fallback`, [matching_weights](../matching_weights/README.md)):
  - E02 renames `adapters_memory` to `storage`. Its classes keep their names
    and bodies, but the module no longer matches, and the match confidence of
    `FixedClock.__init__` drops to 0.70 (name 1.0, AST 1.0, module 0.0), under
    the threshold of 0.80. The adapters had no counterpart
    (`required_target_missing` for `implements_protocol` and its runtime
    part); each is now the only class of its name in the target and is
    paired by it, its methods through it.
  - E03 puts both driven adapters into one module, with the same outcome.
  - E06 turned `Loan` into a dataclass and failed before the probe counted
    the `__init__` that `dataclasses` generates as code of `domain.py` (see
    above): the edge `application -> domain` was then missing.
- import-linter has no matching: its `layers` contract requires every layer
  to exist, so it reports an error on E02 and E03. The static
  `enforce_layers` names the target's modules by the reference modules they
  were matched to and passes both.

## Limits of this evaluation

The limits of the [first program](../architectural_mutants/README.md#limits-of-this-evaluation)
hold here as well: one author wrote the program, the reference, the mutants
and the equivalent rewrites, and the numbers show which kinds of violation
each kind of rule can see, not detection rates on real submissions.
