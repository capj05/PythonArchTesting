# DYN001 — runtime layering showcase

The reference is a three-layer package: `controller` → `service` →
`repository`. The controller receives the service as a parameter (dependency
injection), so its source names no layer the static import graph could check:
every target here imports exactly the same modules. Whether the controller
goes through the service, or reaches past it into the repository, only shows
when it runs.

```bash
python-arch-test --source example/rule_showcase/dyn001_layers/reference \
    --targets-dir example/rule_showcase/dyn001_layers/assignments \
    --format json --dynamic
```

## Marker matrix exercised

| Reference entity            | Marker                                           | Layering rule                         |
|-----------------------------|--------------------------------------------------|---------------------------------------|
| `controller:handle_order`   | `require_runtime_calls("service", cases=[...])`  | the controller must delegate to the service |
| `controller:handle_order`   | `forbid_runtime_calls("repository", cases=[...])`| the controller must not call storage  |

The single case builds the injected objects from the target's own classes with
`$new` and only drives the call; its result is not checked.

## Target index

| Target                            | Expected | What it isolates                                                              |
|-----------------------------------|----------|-------------------------------------------------------------------------------|
| `target_pass_basic`               | PASS     | Same layering as the reference                                                |
| `target_pass_other_pricing`       | PASS     | Different results (rounded totals, cents, another status) — logic is not checked |
| `target_fail_bypass_service`      | FAIL     | Reads `service.repository.get(...)` directly: forbid fails, require passes   |
| `target_fail_logic_in_controller` | FAIL     | Sums the prices itself and never calls the service: require fails            |

Targets do not carry `__archtest__` metadata; the markers live only on the
reference side.

See `findings.md` for the expected vs observed verdicts.
