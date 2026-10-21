# FLW002 — findings

## Expected vs. observed

With `--dynamic`:

| Target | Expected | Observed | Status |
|---|---|---|---|
| `target_pass_basic` | PASS | exit=0, 1 OK | OK |
| `target_pass_other_means` | PASS | exit=0, 1 OK | OK |
| `target_fail_skips_validation` | FAIL | exit=1, 1 FAIL: `case 0: stage 'validated' calls validate() after ['parsed'], but the target never calls it; target calls: ['parse', 'enrich', 'store']` | OK |
| `target_fail_enrich_before_validate` | FAIL | exit=1, 1 FAIL: `case 0: stage 'enriched' calls enrich() after ['parsed', 'validated'], but the target calls it only earlier; target calls: ['parse', 'enrich', 'validate', 'store']` | OK |

Every passing result's summary ends with `stage(s) 'received' call no
project function and were not checked`. The reference run against itself passes.
Without `--dynamic` every target exits 0 with the rule `SKIPPED`.

## Capabilities exercised

- Stages identified by the project functions they call, so the target needs
  no markers and its values are irrelevant: `target_pass_other_means`
  computes another record and passes.
- Calls made below the checked function count: `_prepare` reaches `parse`
  and `validate` for `target_pass_other_means`.
- A reordered pipeline fails even though its final record equals the
  reference's (`target_fail_enrich_before_validate`).

## Limitations / gotchas

- A stage that calls no function of the project (`record = line`, or only
  builtins such as `str.strip`) cannot be recognised in a target and is
  reported as not checked; when no stage calls one, the rule is an `ERROR`.
- Functions are compared by name after entity matching, so a step the target
  renamed is recognised only if matching pairs it with the reference's.
- Only the cases' paths run; a stage on a branch the cases skip is reported
  by the reference run as never reached (`ERROR`).

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
