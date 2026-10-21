# DYN008 — design-pattern showcase

Three classic patterns in one reference module, `patterns.py`, each checked
by what the code does at run time rather than how it is written:

- **Singleton** — `AppConfig.instance()` returns one shared object
  (`is_runtime_singleton`);
- **Observer** — a listener registered with `EventBus.subscribe` is called by
  `publish` and not after `unsubscribe` (`enforce_runtime_observer`); the
  probe registers its own recording listener;
- **Strategy** — `PriceCalculator.total` delegates the discount to the
  injected strategy (`require_runtime_delegation`); the case injects a spy
  with `{"$spy": "strategy"}`.

```bash
python-arch-test --source example/rule_showcase/dyn008_patterns/reference \
    --targets-dir example/rule_showcase/dyn008_patterns/assignments \
    --format json --dynamic
```

## Marker matrix exercised

| Reference entity                     | Marker                                                                  |
|--------------------------------------|-------------------------------------------------------------------------|
| `patterns:AppConfig`                 | `is_runtime_singleton(access="instance", cases=[...])`                   |
| `patterns:EventBus`                  | `enforce_runtime_observer(subscribe=..., notify=..., unsubscribe=..., ...)` |
| `patterns:PriceCalculator.total`     | `require_runtime_delegation("strategy", member="apply", init={...}, ...)` |

## Target index

| Target                                | Expected | What it isolates                                                           |
|---------------------------------------|----------|----------------------------------------------------------------------------|
| `target_pass_basic`                   | PASS     | Same implementations as the reference                                      |
| `target_pass_other_implementations`   | PASS     | `__new__` singleton, dict of listeners, own summing and rounding           |
| `target_fail_new_instance_each_time`  | FAIL     | `instance()` returns `cls()`                                               |
| `target_fail_unsubscribe_ignored`     | FAIL     | `unsubscribe` does nothing                                                 |
| `target_fail_hardcoded_discount`      | FAIL     | Stores the strategy but applies a fixed 10 % itself                        |

Targets do not carry `__archtest__` metadata; the markers live only on the
reference side.

See `findings.md` for the expected vs observed verdicts.
