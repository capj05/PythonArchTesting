# FLW002 — runtime `enforce_flow` showcase

The reference labels the stages a record passes through with `flow(...)`
markers, as the static FLW001 showcase does, and adds `cases=` to
`enforce_flow`. With `--dynamic`:

1. the reference runs on each case and records which of the project's own
   functions each stage calls: `parse`, `validate`, `enrich`, `store`;
2. the target runs the same case and must call those functions in the same
   stage order, at any depth and with any other calls in between.

Values are never recorded or compared. A target whose steps compute other
results passes, and one that ends with exactly the reference's record fails
if it got there in another order. The targets carry no markers.

```bash
python-arch-test --source example/rule_showcase/flw002_runtime_flow/reference \
    --targets-dir example/rule_showcase/flw002_runtime_flow/assignments \
    --format json --dynamic
```

## Marker matrix exercised

| Reference entity | Marker |
|---|---|
| `pipeline:import_record` | `enforce_flow(["received", "parsed", "validated", "enriched", "stored"], variable="record", cases=[...])` |

The stage `received` (`record = line`) calls no project function, so a
target's version of it cannot be recognised; every result says it was not
checked.

## Target index

| Target | Expected | What it isolates |
|---|---|---|
| `target_pass_basic` | PASS | Same steps in the same order |
| `target_pass_other_means` | PASS | `parse` and `validate` reached through a helper, another variable name, steps that compute different values |
| `target_fail_skips_validation` | FAIL | Never calls `validate` |
| `target_fail_enrich_before_validate` | FAIL | Calls every step, `enrich` before `validate`; the final record equals the reference's |

Without `--dynamic` every rule is `SKIPPED`.

See `findings.md` for the observed verdicts.
