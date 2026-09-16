# API005 — findings

## Expected vs. observed

| Target                            | Expected | Observed              | Status |
|-----------------------------------|----------|-----------------------|--------|
| `target_pass_basic`               | PASS     | exit=0, 4 OK          | OK     |
| `target_pass_regex_match`         | PASS     | exit=0, 4 OK          | OK     |
| `target_pass_classmethod_only`    | PASS     | exit=0, 4 OK          | OK     |
| `target_fail_below_min`           | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |
| `target_fail_above_max`           | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |
| `target_fail_wrong_method_kind`   | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |
| `target_fail_declared_only`       | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |

## Capabilities exercised

- `name_match="regex"` with arbitrary patterns (e.g. `^handle_.*$`).
- `name_match="names"` with an explicit list.
- `min_count` / `max_count` cardinality bounds.
- `declared_only=True` filtering inherited methods.
- `method_kind` filter (instance / classmethod / staticmethod).

## Parameter values discovered during validation

- `name_match` valid values: `"any"`, `"regex"`, `"names"` (NOT `"alias"` —
  that is the spelling used by `does_not_have`).
- `names` must be a **list**, not a tuple. Passing a tuple raises
  `compiler_invalid_declaration: "names must be a list of non-empty
  strings"` and the rule is silently dropped.
- `method_kind` valid values: `"any"`, `"instance"`, `"classmethod"`,
  `"staticmethod"` (NOT `"class"` / `"static"`).

## Limitations observed

(none currently)

## Fix history

### LIMITATION-1 — invalid params silently drop the rule (FIXED)

**Original symptom**: a misconfigured `require_method_set` rule (invalid
`name_match`, `method_kind`, `min_count`/`max_count`, `names` as tuple
instead of list, etc.) emitted a `compiler_invalid_declaration`
diagnostic, but per-target evaluations did not produce any rule result.
A naive reader of `summary.results.status_counts` saw "all OK" and
missed that an entire rule had been silently dropped.
`--validate-declarations` was the only existing surface for the issue.

**Resolution**: the same sentinel-rule pattern that fixed API004 has
been applied here. Each invalid-declaration branch in
`compile_require_method_set` now emits a synthetic
`Rule(rule_type="compiler_invalid_param", ...)` alongside the compiler
evidence. The decorator-agnostic `CompilerInvalidParamEvaluator` always
returns FAILED, so the dropped rule appears in `status_counts` and in
the per-target output with a useful fix hint.

**Generalized helper**: the API004-specific
`_invalid_param_sentinel_rule` was promoted to
`pythonarchtesting.rules.compilation.common.build_invalid_param_sentinel_rule`
and is parameterised by `decorator_name` and `rule_id_prefix` so future
families (API006, NEG001) can reuse it directly.

**Sentinel `rule_id` shape**:
`API005/require_method_set/invalid_declaration/<param>[<suffix>]`,
where `<param>` is the offending parameter name (e.g. `name_match`,
`method_kind`, `min_count`, `target_kind` for non-class placement).

## Validation declaration check

`--validate-declarations` reports 0 diagnostics after the parameter fixes
above.
