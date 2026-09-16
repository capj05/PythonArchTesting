# API006 — findings

## Expected vs. observed

| Target                              | Expected | Observed              | Status |
|-------------------------------------|----------|-----------------------|--------|
| `target_pass_basic`                 | PASS     | exit=0, 4 OK          | OK     |
| `target_pass_dataclass_fields`      | PASS     | exit=0, 4 OK          | OK     |
| `target_pass_property_count`        | PASS     | exit=0, 4 OK          | OK     |
| `target_fail_below_min`             | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |
| `target_fail_above_max`             | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |
| `target_fail_member_kind_mismatch`  | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |
| `target_fail_no_property_allowed`   | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |

## Capabilities exercised

- `member_kinds` filter — `attribute`, `dataclass_field`, `property`,
  `cached_property`, descriptors.
- `min_count` / `max_count` cardinality enforcement.
- `name_match` regex/names matching consistent with API005.
- Property + dataclass-field interpretations co-exist (a class can satisfy
  rules that target either kind, on different members).

## Limitations / gotchas

(none currently)

## Fix history

### LIMITATION-1 — invalid params silently drop the rule (FIXED)

**Original symptom**: a misconfigured `require_member_set` rule (invalid
`member_kinds`, `name_match`, `storage`, `descriptor_kinds`,
`constructor_kind`, `method_kind`, `min_count`/`max_count`, `names` as
tuple instead of list, etc.) emitted a `compiler_invalid_declaration`
diagnostic but per-target evaluations did not produce any rule result.
A naive reader of `summary.results.status_counts` saw "all OK" and
missed that an entire rule had been silently dropped.
`--validate-declarations` was the only existing surface for the issue.

**Resolution**: the same sentinel-rule pattern that fixed API004 and
API005 has been applied here. Each invalid-declaration branch in
`compile_require_member_set` now emits a synthetic
`Rule(rule_type="compiler_invalid_param", ...)` alongside the compiler
evidence. The decorator-agnostic `CompilerInvalidParamEvaluator` always
returns FAILED, so the dropped rule appears in `status_counts` and in
the per-target output with a useful fix hint.

**Reused helper**:
`pythonarchtesting.rules.compilation.common.build_invalid_param_sentinel_rule`
(introduced in the API005 fix) is parameterised by `decorator_name` and
`rule_id_prefix`, so this fix required no new infrastructure.

**Sentinel `rule_id` shape**:
`API006/require_member_set/invalid_declaration/<param>[<suffix>]`,
where `<param>` is the offending parameter name (e.g. `member_kinds`,
`name_match`, `storage`, `descriptor_kinds`, `constructor_kind`,
`method_kind`, `min_count`, `max_count`, `target_kind` for non-class
placement).

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
