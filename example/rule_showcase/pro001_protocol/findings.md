# PRO001 — findings

## Expected vs. observed

| Target                              | Expected | Observed              | Status |
|-------------------------------------|----------|-----------------------|--------|
| `target_pass_basic`                 | PASS     | exit=0, 4 OK          | OK     |
| `target_pass_compatible_extra_param`| PASS     | exit=0, 4 OK          | OK     |
| `target_fail_missing_method`        | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |
| `target_fail_wrong_return`          | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |
| `target_fail_method_kind`           | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |
| `target_fail_exact_signature`       | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |

## Capabilities exercised

- Structural conformance — the target class need not inherit from the
  protocol; any class that exposes the right methods passes.
- Method-level signature compatibility (default mode) — extra optional
  parameters in the target are accepted.
- Return-annotation enforcement — incompatible return type fails the
  rule even when method names line up.
- Method kind enforcement — a `@classmethod` declared in the protocol
  cannot be satisfied by an instance method (and vice versa).
- `signature_mode="exact"` — when set on the protocol, the target must
  match the exact parameter list, rejecting the extra-param target that
  would have passed under default compatibility mode.

## Limitations / gotchas

- `implements_protocol` resolves the protocol type through the matched
  source-target entity table (same machinery as `subclass_of`). The
  protocol declared in the reference must therefore be itself analysable
  — passing a protocol from outside the source tree does not work.
- Like API001/API002, the underlying signature comparison runs through
  the `annotation_compatibility` evaluator. Quirks observed there
  (`return_annotation="ignore"` not honored on return-only rules) do not
  apply here because the protocol path always ties parameter and return
  checks together.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
