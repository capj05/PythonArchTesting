# DYN003 — findings

## Expected vs. observed

With `--dynamic`:

| Target                       | Expected | Observed                                                                                 | Status |
|------------------------------|----------|------------------------------------------------------------------------------------------|--------|
| `target_pass_basic`          | PASS     | exit=0, 1 OK                                                                             | OK     |
| `target_pass_other_order`    | PASS     | exit=0, 1 OK, with `no case ran lines 16-18 of bank.py, so they were not checked`        | OK     |
| `target_fail_direct_balance` | FAIL     | exit=1, 1 FAIL: `case 0: bank:transfer sets Account.balance at bank.py:9 (+1 more)`      | OK     |
| `target_fail_helper_write`   | FAIL     | exit=1, 1 FAIL: `case 0: bank:_move sets Account.balance at bank.py:13`                  | OK     |

Without `--dynamic` every target exits 0 with the rule `SKIPPED`.

## Capabilities exercised

- Assignments attributed to the code that made them, with file and line.
- A write hidden in a helper function of the same module.
- Writes by `Account.__init__`, `deposit`, and `withdraw` are the class's own
  and are allowed.
- A different order of operations is not a structural difference.
- Coverage of a pass: the single case never fails a withdrawal, so the
  rollback in `target_pass_other_order` (lines 16-18) never runs, and the
  summary says those lines were not checked. A case with an amount larger
  than the balance would cover them.

## Limitations / gotchas

- Mutating a contained object (`account.history.append(...)`) is not an
  attribute assignment and is not seen.
- `object.__setattr__(obj, ...)` and writes to `obj.__dict__` bypass the check.
- Only classes defined in the analysed project are watched.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
