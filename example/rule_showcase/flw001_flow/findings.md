# FLW001 — findings

## Expected vs. observed

| Target                              | Expected | Observed              | Status |
|-------------------------------------|----------|-----------------------|--------|
| `target_pass_linear`                | PASS     | exit=0, 2 OK          | OK     |
| `target_pass_with_branch`           | PASS     | exit=0, 2 OK          | OK     |
| `target_fail_missing_stage`         | FAIL     | exit=1, 1 OK / 1 FAIL | OK     |
| `target_fail_out_of_order`          | FAIL     | exit=1, 1 OK / 1 FAIL | OK     |
| `target_fail_branch_skips_stage`    | FAIL     | exit=1, 1 OK / 1 FAIL | OK     |

## Capabilities exercised

- Linear flow — every stage marker is visited in declared order.
- Branch flow — `enforce_flow` with stages reachable through either
  branch of an `if`/`else`, with a final stage joined after the merge.
- Negative cases:
  - missing stage — declared stage absent in the target.
  - out-of-order — stages present but in the wrong sequence.
  - branch skipping a required stage — one branch returns early and
    misses the final stage.

## Important: target must repeat the markers

The `flow` evaluator inspects the **target's** AST for the `flow(...)`
markers; the reference's markers only describe the *expected* order /
membership. A target that drops the markers fails with
`missing_stages` even when the underlying control flow is correct.

This means the showcase target files mirror the reference structurally
*and* preserve the `__archtest__: Annotated[None, flow(<stage>)]`
annotations — see `assignments/target_pass_linear/pipelines.py` for the
template.

## Limitations / gotchas

- Each `flow(...)` marker must be tied to a specific `variable=` to
  participate in the per-variable CFG analysis used by `enforce_flow`.
- The marker line is matched as a Python `__archtest__` annotation;
  repeated markers in the same scope require `# noqa: F811` to silence
  the redefinition warning from flake8.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
