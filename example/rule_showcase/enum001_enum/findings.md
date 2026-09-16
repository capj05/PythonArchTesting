# ENUM001 — findings

## Expected vs. observed

| Target                          | Expected | Observed              | Status |
|---------------------------------|----------|-----------------------|--------|
| `target_pass_basic`             | PASS     | exit=0, 5 OK          | OK     |
| `target_pass_int_enum`          | PASS     | exit=0, 5 OK          | OK     |
| `target_pass_str_enum`          | PASS     | exit=0, 5 OK          | OK     |
| `target_pass_flag_enum`         | PASS     | exit=0, 5 OK          | OK     |
| `target_pass_transitive_enum`   | PASS     | exit=0, 5 OK          | OK     |
| `target_fail_regular_class`     | FAIL     | exit=1, 4 OK / 1 FAIL | OK     |

## Capabilities exercised

- Plain `enum.Enum` subclass detection.
- `enum.IntEnum`, `enum.StrEnum`, `enum.Flag` — all recognized as enums.
- Transitive inheritance: a class that inherits from a user-defined enum
  base (which itself inherits from `enum.Enum`) is still detected.
- Negative case: a regular class fails the rule with a clear verdict.

## Limitations / gotchas

- The rule cares only about the enum-ness of the resolved type; it does
  not differentiate between `enum.Enum` flavours (Int / Str / Flag) — if
  the contract requires a specific flavour, combine `is_enum` with a
  `subclass_of("IntEnum")` rule.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
