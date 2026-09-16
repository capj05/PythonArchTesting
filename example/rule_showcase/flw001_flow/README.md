# FLW001 — `flow` / `enforce_flow` showcase

The reference module annotates two functions with in-body `flow(...)` stage
markers and a single `enforce_flow(...)` declaration each. The evaluator
(`execution.evaluators.variable_flow`) builds a CFG of the *target* function
body and verifies that the assignments to the named variables form the declared
stage sequence on every path.

`flow(stage, *, variable=...)` — tags one stage at a point in the CFG (severity
is always INFO). `enforce_flow(stages, *, variable=..., severity="error")`
requires the listed stages to occur in the declared order on every path from
entry to exit. Multiple `__archtest__: Annotated[None, ...]` lines may appear
inside a function body — each becomes its own `AnnAssign` node and they don't
collide.

## Reference functions and their stage sequences

| Reference function   | Stage markers (in order)                          | `enforce_flow` requirement              |
|----------------------|---------------------------------------------------|-----------------------------------------|
| `linear_pipeline`    | `acquired` (raw), `cleaned` (cleaned), `saved` (saved_id) | `("acquired", "cleaned", "saved")` |
| `branched_pipeline`  | `start` (counter), `branch_a` or `branch_b`, `end` (counter) | `("start", "end")`              |

## Target index

| Target                              | Expected verdict | What it isolates                                                       |
|-------------------------------------|------------------|------------------------------------------------------------------------|
| `target_pass_linear`                | PASS             | Both functions verbatim — declared ordering preserved                  |
| `target_pass_with_branch`           | PASS             | `branched_pipeline` — both branches still reach the final `end` step    |
| `target_fail_missing_stage`         | FAIL             | `linear_pipeline` drops the `cleaned = raw.strip()` step (no `cleaned`) |
| `target_fail_out_of_order`          | FAIL             | `linear_pipeline` assigns `saved_id` before `cleaned` (wrong order)     |
| `target_fail_branch_skips_stage`    | FAIL             | `branched_pipeline` removes the final `counter = counter * 2` (`end`)   |

Targets carry no `__archtest__` annotations — the rule lives on the reference
side and the evaluator inspects the target's CFG and variable assignments.

## How to re-run

```bash
python-arch-test --validate-declarations \
    --source example/rule_showcase/flw001_flow/reference

for t in target_pass_linear target_pass_with_branch \
         target_fail_missing_stage target_fail_out_of_order \
         target_fail_branch_skips_stage; do
  python-arch-test \
      --source example/rule_showcase/flw001_flow/reference \
      --target example/rule_showcase/flw001_flow/assignments/$t \
      --format json \
      --output example/rule_showcase/flw001_flow/reports/$t.report.json
done
```

See `findings.md` (added after the parent runs the validation matrix) for the
expected/observed verdict cross-check.
