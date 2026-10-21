# DYN001 — findings

## Expected vs. observed

With `--dynamic`:

| Target                            | Expected | Observed                                                                                         | Status |
|-----------------------------------|----------|--------------------------------------------------------------------------------------------------|--------|
| `target_pass_basic`               | PASS     | exit=0, 2 OK                                                                                     | OK     |
| `target_pass_other_pricing`       | PASS     | exit=0, 2 OK                                                                                     | OK     |
| `target_fail_bypass_service`      | FAIL     | exit=1, 1 FAIL / 1 OK: `case 0: handle_order calls repository:OrderRepository.get (line 17)`     | OK     |
| `target_fail_logic_in_controller` | FAIL     | exit=1, 1 FAIL / 1 OK: `case 0: no direct call into service`                                     | OK     |

Without `--dynamic` every target exits 0 with both rules `SKIPPED`.

## Capabilities exercised

- Calls through an injected object whose type the source does not state.
- Objects for the call built from the target's own classes (`$new`).
- The two directions of a layering rule: a layer that must be used and one that
  must not be reached.
- Results that differ from the reference do not matter.

## Limitations / gotchas

- Only direct calls from the controller module count: the service's own call
  into the repository is not the controller's.
- The case must reach the code path that uses the layers; a branch no case
  takes is not observed.
- Cases are literals inside each marker; markers are read without executing
  the reference, so a shared constant cannot be used.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
