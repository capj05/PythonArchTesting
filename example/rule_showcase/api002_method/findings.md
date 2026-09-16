# API002 — findings

## Expected vs. observed

| Target                            | Expected | Observed              | Status |
|-----------------------------------|----------|-----------------------|--------|
| `target_pass_basic`               | PASS     | exit=0, 7 OK          | OK     |
| `target_pass_alias_match`         | PASS     | exit=0, 7 OK          | OK     |
| `target_pass_inherited`           | PASS     | exit=0, 7 OK          | OK     |
| `target_fail_missing_method`      | FAIL     | exit=1, 6 OK / 1 FAIL | OK     |
| `target_fail_wrong_signature`     | FAIL     | exit=1, 6 OK / 1 FAIL | OK     |
| `target_fail_method_kind_mismatch`| FAIL     | exit=1, 6 OK / 1 FAIL | OK     |
| `target_fail_declared_only`       | FAIL     | exit=1, 6 OK / 1 FAIL | OK     |

## Capabilities exercised

- exact name match + alias-list match (`name_match="alias"`)
- `declared_only=True` filtering inherited methods
- `method_kind` distinguishing instance/classmethod/staticmethod
- `allow_inherited` opt-in for transitive resolution

## Limitations / gotchas

- `required_method` evaluates only against the matched class entity. If the
  matcher fails to pair the source class to any target class, the rule never
  fires — this is by design but means class-level failures are reported as
  "target missing", not "method missing".

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
