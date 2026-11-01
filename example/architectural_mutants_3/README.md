# Architectural mutants, program 3: the clinic

A third program for the architectural-mutant evaluation, larger and deeper
than the first two: about 740 lines in 17 modules, the layers being
subpackages (`clinic.domain.schedule` is `domain/schedule.py`). Patients book,
cancel and move appointments with a doctor; a confirmation goes out through
an event bus, and reminders the day before. It tests whether what the first
two programs showed holds when module names have dots, layers are packages,
and a use case calls through several modules of its own layer.

- `solution/` — the program: `domain` (patients, slots and appointments,
  cancellation policies, events), `ports` (stores, notifier and clock as
  protocols), `application` (booking, reminders, the event bus), `adapters`
  (in-memory and SQLite stores, an outbox notifier, clocks), `api` (request
  handlers and serializers), and `wiring` (the composition root, with
  `serve(requests)`, which builds the application and answers a list of
  requests).
- `reference/` — the same code with the markers that state the intents below.
- `model/__init__.py` — the model mode's only marker: `architecture_entry`
  on `wiring.serve`, run on one sequence of requests (book, a taken slot, a
  late booking, move, free slots, reminders, a late and an early cancel, an
  unknown action) on the in-memory store and on SQLite.
- `mutants.py` — 19 mutants and 8 equivalent rewrites.

## Intents

| # | Intent | Markers in `reference/` |
|---|---|---|
| J1 | `domain` depends on nothing outside it, no I/O library | `forbid_imports` on the `domain` package, `enforce_layers` |
| J2 | `application` depends on `domain` and `ports` only, never on `adapters` | `forbid_imports` on the `application` package, `enforce_layers` |
| J3 | the handlers talk to the application only | `forbid_imports` on the `api` package, `require_runtime_calls`, `forbid_runtime_calls` (transitive, through `application`), runtime `enforce_layers` |
| J4 | SQL only in `adapters.sqlite_store` | `forbid_imports` (application, api, domain), `forbid_runtime_imports` on `application.booking` |
| J5 | the adapters satisfy their ports | `implements_protocol`, `implements_runtime_protocol` |
| J6 | adapters are built only in `wiring` | `forbid_runtime_instantiation` in the use cases and the `book` handler |
| J7 | events go through the bus; the reminders notify through the port | `enforce_runtime_observer` on `EventBus`, `require_runtime_delegation` on `on_booked`, `run_for` |
| J8 | the cancellation policy is injected | `require_runtime_delegation("policy")`, `forbid_runtime_instantiation("domain.policies")` on `cancel` |
| J9 | no cycle between modules | `forbid_cycles` (static and runtime) |
| J10 | `domain.schedule` is used through `Slot`, `Appointment`, `free_slots`, `WORKING_HOURS` | `module_interface` |
| J11 | an appointment changes only through its own methods | `forbid_foreign_writes` on `cancel`, `move` |

The layer order (root `__init__.py`): `wiring`, then `api | adapters`
(independent of each other), `application`, `ports`, `domain`.

## Running

```bash
python example/architectural_mutants/run.py --program example/architectural_mutants_3
```

## Results

See `results.md`; the findings are summarised in the F5 evaluation note.
