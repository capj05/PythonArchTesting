# DYN003 — `forbid_foreign_writes` showcase

The reference package has an `Account` class that guards its balance in
`withdraw` and `deposit`, and a `bank.transfer` function that must move money
by asking the accounts — never by assigning `account.balance` itself. Python
has no private attributes, so the rule watches which code assigns attributes
while `transfer` runs.

```bash
python-arch-test --source example/rule_showcase/dyn003_encapsulation/reference \
    --targets-dir example/rule_showcase/dyn003_encapsulation/assignments \
    --format json --dynamic
```

## Marker matrix exercised

| Reference entity | Marker                               | What it enforces                                        |
|------------------|--------------------------------------|---------------------------------------------------------|
| `bank:transfer`  | `forbid_foreign_writes(cases=[...])` | `Account` attributes are set only by `Account` methods |

## Target index

| Target                       | Expected | What it isolates                                                          |
|------------------------------|----------|---------------------------------------------------------------------------|
| `target_pass_basic`          | PASS     | Uses `withdraw` and `deposit`, as the reference does                     |
| `target_pass_other_order`    | PASS     | Credits first, debits second, rolls back on error — still encapsulated   |
| `target_fail_direct_balance` | FAIL     | `source.balance -= amount` straight from `transfer`                       |
| `target_fail_helper_write`   | FAIL     | The assignment hides in a module-level helper `_move`                     |

Targets do not carry `__archtest__` metadata; the markers live only on the
reference side.

See `findings.md` for the expected vs observed verdicts.
