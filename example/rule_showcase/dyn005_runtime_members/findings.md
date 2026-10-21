# DYN005 — findings

## Expected vs. observed

With `--dynamic`:

| Target                        | Expected | Observed                                                                                  | Status |
|-------------------------------|----------|-------------------------------------------------------------------------------------------|--------|
| `target_pass_explicit`        | PASS     | exit=0, 2 OK                                                                              | OK     |
| `target_pass_mixin`           | PASS     | exit=0, 2 OK                                                                              | OK     |
| `target_fail_missing_port`    | FAIL     | exit=1, 1 FAIL / 1 OK: `case 0: the instance has no 'debug' (+4 more)`                   | OK     |
| `target_fail_stores_password` | FAIL     | exit=1, 1 FAIL / 1 OK: `case 0: the instance has 'password' (from instance)`              | OK     |

The reference run against itself passes. Without `--dynamic` every target
exits 0 with both rules `SKIPPED`.

## Capabilities exercised

- Attributes created by `setattr` in a loop and by `__dict__.update`, which
  the static attribute rules do not see.
- Members found on a mixin's class attributes count as present.
- Several cases build several instances; each must satisfy the rule.

## Limitations / gotchas

- Only the instance right after construction is inspected.
- The member's type and value are not checked.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
