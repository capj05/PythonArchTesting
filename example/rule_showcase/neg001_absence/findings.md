# NEG001 — findings

## Expected vs. observed

| Target                          | Expected | Observed              | Status |
|---------------------------------|----------|-----------------------|--------|
| `target_pass_basic`             | PASS     | exit=0, 5 OK          | OK     |
| `target_pass_inherited_allowed` | PASS     | exit=0, 5 OK          | OK     |
| `target_fail_explicit_name`     | FAIL     | exit=1, 4 OK / 1 FAIL | OK     |
| `target_fail_regex_match`       | FAIL     | exit=1, 4 OK / 1 FAIL | OK     |
| `target_fail_alias`             | FAIL     | exit=1, 4 OK / 1 FAIL | OK     |
| `target_fail_member_kind`       | FAIL     | exit=1, 4 OK / 1 FAIL | OK     |

## Capabilities exercised

- Explicit name match (`names=[...]`) — fails when any listed name is
  present on the target class.
- Regex match (`name_match="regex"`, `pattern=...`) — fails when any
  member name matches the pattern.
- Alias match (`name_match="alias"` with `aliases=[...]`) — fails when
  the public alias is bound, even if implemented under a different
  internal name.
- Member-kind filter — restricts the absence check to `attribute`,
  `method`, `property`, etc.; presence of a forbidden name in a
  *different* kind does not trigger the rule.
- `target_pass_inherited_allowed` — inherited members of the forbidden
  name are allowed when the rule scopes to declared-only.

## Limitations / gotchas

### `name_match` spelling differs from API005 / API006

`does_not_have` accepts `name_match="alias"` (singular); the
positive-set rules (`require_method_set`, `require_member_set`) accept
`name_match="names"` (plural). Mixing them up emits
invalid-declaration evidence and drops the rule; a
`compiler_invalid_param` sentinel reports it as FAILED.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
