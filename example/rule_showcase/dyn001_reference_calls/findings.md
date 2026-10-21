# DYN001 `enforce_reference_calls` — findings

## Expected vs. observed

With `--dynamic`:

| Target                                  | Expected | Observed                                                                                                   | Status |
|-----------------------------------------|----------|------------------------------------------------------------------------------------------------------------|--------|
| `target_pass_basic`                     | PASS     | exit=0, 1 OK                                                                                               | OK     |
| `target_pass_other_results`             | PASS     | exit=0, 1 OK                                                                                               | OK     |
| `target_fail_bypass_service`            | FAIL     | exit=1, 1 FAIL: `case 0: controller -> repository is not in the reference (handle_order calls repository:OrderRepository.get …)` | OK |
| `target_fail_notifier_reads_repository` | FAIL     | exit=1, 1 FAIL: `case 0: notifier -> repository is not in the reference (Notifier.order_placed calls repository:OrderRepository.get …)` | OK |
| `target_fail_skips_notifier`            | FAIL     | exit=1, 1 FAIL: `case 0: the reference's service -> notifier never happened`                               | OK     |

The reference run against itself passes. Without `--dynamic` every target
exits 0 with the rule `SKIPPED`.

## Capabilities exercised

- The allowed call graph learned from the reference, not written by hand.
- Violations anywhere in the call tree, not only in the marked function.
- A missing layer with `require_all`.
- Reference and targets are packages with different names; module names are
  compared without the package prefix.

## Limitations / gotchas

- Edges, not functions: `service -> repository` is one edge whatever methods
  are called on it.
- Only edges between project modules; calls into the standard library are not
  part of the graph.
- The case has to reach every part of the design that matters; a branch no
  case takes contributes no edges, in the reference or in the target.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
