# DYN001 — `enforce_reference_calls` showcase

The reference is a four-module package: `controller` → `service` →
`repository` and `service` → `notifier`. The layers are wired by injection,
so no target's import graph says who talks to whom. A single marker on the
entry point `controller.handle_order` runs the reference, records every call
between two of its modules, and requires each target to stay within that call
graph (`require_all=True`: and to use all of it).

```bash
python-arch-test --source example/rule_showcase/dyn001_reference_calls/reference \
    --targets-dir example/rule_showcase/dyn001_reference_calls/assignments \
    --format json --dynamic
```

Reference call graph for the case:

```
controller -> service
service    -> repository
service    -> notifier
```

## Marker matrix exercised

| Reference entity          | Marker                                                  | What it enforces                          |
|---------------------------|---------------------------------------------------------|-------------------------------------------|
| `controller:handle_order` | `enforce_reference_calls(require_all=True, cases=[...])`| the reference's module call graph, exactly |

## Target index

| Target                                  | Expected | What it isolates                                                       |
|-----------------------------------------|----------|------------------------------------------------------------------------|
| `target_pass_basic`                     | PASS     | Same layering as the reference                                         |
| `target_pass_other_results`             | PASS     | Rounded totals — different results, same calls                        |
| `target_fail_bypass_service`            | FAIL     | Extra edge at the top: `controller -> repository`                      |
| `target_fail_notifier_reads_repository` | FAIL     | Extra edge two layers down: `notifier -> repository`                   |
| `target_fail_skips_notifier`            | FAIL     | Missing edge `service -> notifier` (caught because of `require_all`)  |

Targets do not carry `__archtest__` metadata; the markers live only on the
reference side.

See `findings.md` for the expected vs observed verdicts.
