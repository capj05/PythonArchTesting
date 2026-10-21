# DYN008 — findings

## Expected vs. observed

With `--dynamic`:

| Target                                | Expected | Observed                                                                                       | Status |
|---------------------------------------|----------|------------------------------------------------------------------------------------------------|--------|
| `target_pass_basic`                   | PASS     | exit=0, 3 OK                                                                                   | OK     |
| `target_pass_other_implementations`   | PASS     | exit=0, 3 OK                                                                                   | OK     |
| `target_fail_new_instance_each_time`  | FAIL     | exit=1, 1 FAIL / 2 OK: `case 0: two accesses via instance returned different objects`          | OK     |
| `target_fail_unsubscribe_ignored`     | FAIL     | exit=1, 1 FAIL / 2 OK: `case 0: the listener was still called after unsubscribe()`             | OK     |
| `target_fail_hardcoded_discount`      | FAIL     | exit=1, 1 FAIL / 2 OK: `case 0: never delegated to strategy.apply()`                           | OK     |

The reference run against itself passes. Without `--dynamic` every target
exits 0 with all rules `SKIPPED`.

## Capabilities exercised

- Pattern conformance independent of implementation technique.
- A probe-made listener that works whether the subject calls it directly or
  through a method.
- A spy injected through the constructor (`init`) of the method's instance.

## Limitations / gotchas

- `AppConfig()` can still create a second instance; only the declared access
  path is checked.
- The spy returns its first argument; a strategy expected to return something
  else may make the code fail after delegating, which is reported, not judged.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
