# DYN004 — `forbid_runtime_instantiation` showcase

The reference `OrderService` receives its repository in the constructor
(dependency injection). It may call the repository and create its own domain
objects (`models.Order`, a dataclass), but must never build an
`OrderRepository` itself. All targets call the same repository methods, so
only the creation tells them apart.

```bash
python-arch-test --source example/rule_showcase/dyn004_injection/reference \
    --targets-dir example/rule_showcase/dyn004_injection/assignments \
    --format json --dynamic
```

## Marker matrix exercised

| Reference entity           | Marker                                                                | What it enforces                                  |
|----------------------------|-----------------------------------------------------------------------|---------------------------------------------------|
| `service:OrderService.place` | `forbid_runtime_instantiation("repository", init={...}, cases=[...])` | the repository is injected, never created here |

`init` injects the repository with `$new`; that object is built by the case,
not by the target, and does not count.

## Target index

| Target                         | Expected | What it isolates                                                        |
|--------------------------------|----------|-------------------------------------------------------------------------|
| `target_pass_basic`            | PASS     | Uses the injected repository, creates `Order` objects                   |
| `target_pass_other_internals`  | PASS     | No `Order` at all, a dict instead — internals differ, injection holds   |
| `target_fail_builds_in_init`   | FAIL     | Ignores the argument and builds its own repository in `__init__`        |
| `target_fail_builds_in_method` | FAIL     | Builds a fresh repository inside `place`                                |

Targets do not carry `__archtest__` metadata; the markers live only on the
reference side.

See `findings.md` for the expected vs observed verdicts.
