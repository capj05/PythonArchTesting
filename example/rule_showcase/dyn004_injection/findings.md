# DYN004 — findings

## Expected vs. observed

With `--dynamic`:

| Target                         | Expected | Observed                                                                                                       | Status |
|--------------------------------|----------|----------------------------------------------------------------------------------------------------------------|--------|
| `target_pass_basic`            | PASS     | exit=0, 1 OK                                                                                                   | OK     |
| `target_pass_other_internals`  | PASS     | exit=0, 1 OK                                                                                                   | OK     |
| `target_fail_builds_in_init`   | FAIL     | exit=1, 1 FAIL: `case 0: service:OrderService.__init__ creates repository:OrderRepository at service.py:18`     | OK     |
| `target_fail_builds_in_method` | FAIL     | exit=1, 1 FAIL: `case 0: service:OrderService.place creates repository:OrderRepository at service.py:17`        | OK     |

The reference run against itself passes. Without `--dynamic` every target
exits 0 with the rule `SKIPPED`.

## Capabilities exercised

- Construction while the method's instance is built (`__init__`), not only
  during the call.
- Objects injected by the case (`$new`) are not counted against the target.
- Creating other project objects (`models.Order`, dataclass-generated
  `__init__`) stays allowed.

## Limitations / gotchas

- Only classes of the analysed project are watched; a `sqlite3.connect()`
  inside the service is a call, use `forbid_runtime_calls` for it.
- A repository created by another module (a factory) on the service's behalf
  is the factory's, not the service's.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
