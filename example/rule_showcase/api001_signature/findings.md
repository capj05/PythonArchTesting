# API001 — findings

## Expected vs. observed

| Target                              | Expected | Observed                               | Status |
|-------------------------------------|----------|----------------------------------------|--------|
| `target_pass_basic`                 | PASS     | exit=0, 13 OK                          | OK     |
| `target_pass_extras_compatible`     | PASS     | exit=0, 13 OK                          | OK     |
| `target_pass_renamed`               | PASS     | exit=0, 13 OK                          | OK     |
| `target_pass_return_ignore_drift`   | PASS     | exit=0, 13 OK                          | OK     |
| `target_fail_missing_param`         | FAIL     | exit=1, 11 OK / 1 FAILED / 1 SKIPPED   | OK     |
| `target_fail_renamed_forbidden`     | FAIL     | exit=1, 12 OK / 1 FAILED               | OK     |
| `target_fail_exact_extras`          | FAIL     | exit=1, 11 OK / 1 FAILED / 1 SKIPPED   | OK     |
| `target_fail_wrong_return`          | FAIL     | exit=1, 12 OK / 1 FAILED               | OK     |

Each function with a declared return type produces 2 results (param-shape
rule + return-only rule); `return_ignore` (declared with
`return_annotation="ignore"`) produces 1 result. 6×2 + 1×1 = 13 results
per target.

## Defects observed

None — all targets behave as expected after the DEFECT-1 / DEFECT-2 / CLI
quirk fixes (see "Fix history" below).

## Other observations

- `mode="exact"` correctly rejects extra parameters (`target_fail_exact_extras`
  → FAILED on `exact_strict`).
- `allow_param_rename=False` correctly rejects renames (`target_fail_renamed_forbidden`
  → FAILED on `rename_forbidden`).
- `return_annotation="error"` correctly escalates a return mismatch to
  FAILED (`target_fail_wrong_return` on `must_keep_return`).
- `return_annotation="ignore"` (alias for `"off"`) suppresses the
  return-only sibling rule entirely; declarations using `"ignore"` no
  longer emit a return-shape result.
- The default value of `return_annotation` is `"warning"` per the
  compiler, so by default the return-only rule is a separate
  `severity="warning"` result.
- `target_pass_basic` shows the framework runs cleanly when signatures
  match exactly across all parameter combinations.
- `target_pass_extras_compatible` exercises the rule-aware re-gating in
  `core/evaluation.py`: the matcher returns `low_confidence` because the
  target's `signature_key` differs (extras), but the evaluator is still
  invoked because `allow_extra_params=True` and the divergence is
  extras-only.

## Fix history

- **DEFECT-1** (`allow_extra_params=True` skipped for low-confidence
  matches): fixed in `core/evaluation.py` by promoting low-confidence
  matches to evaluation when the candidate has the same name and the
  signature divergence is extras-only.
- **DEFECT-2** (`return_annotation="ignore"` did not suppress the
  return-only rule): fixed in `rules/compilation/decorators/api_signature.py`
  by accepting `"ignore"` as an alias for `"off"` and emitting a
  `compiler_invalid_param` diagnostic on unrecognised values.
- **CLI quirk** (single-target `--output X.md` wrote `X.md/report.md`):
  fixed in `report/api.py` + `report/renderers/markdown_bundle.py` —
  single-target with `.md` suffix now writes the report directly to the
  given path; multi-target / no-suffix paths still produce a bundle
  directory.

## Validation declaration check

`python-arch-test --validate-declarations --source .../reference` reports
0 diagnostics — the reference module compiles cleanly.
