# DYN005 — runtime members showcase

The reference `Settings` fills `host`, `port`, and `debug` from a dict of
defaults with `setattr` in a loop, so the names never appear as
`self.host = ...`. Two markers check the instance Python actually builds:

- `require_runtime_members("host", "port", "debug", ...)` — every instance has
  them, with or without overrides;
- `forbid_runtime_members("password", ...)` — a password passed in is never
  kept on the object.

```bash
python-arch-test --source example/rule_showcase/dyn005_runtime_members/reference \
    --targets-dir example/rule_showcase/dyn005_runtime_members/assignments \
    --format json --dynamic
```

## Marker matrix exercised

| Reference entity     | Marker                                                  | Cases                                  |
|----------------------|---------------------------------------------------------|----------------------------------------|
| `settings:Settings`  | `require_runtime_members("host", "port", "debug", ...)` | no overrides; a port and a password    |
| `settings:Settings`  | `forbid_runtime_members("password", ...)`               | a port and a password                  |

## Target index

| Target                        | Expected | What it isolates                                                          |
|-------------------------------|----------|---------------------------------------------------------------------------|
| `target_pass_explicit`        | PASS     | Plain `self.x = ...` assignments                                          |
| `target_pass_mixin`           | PASS     | Defaults as class attributes of a mixin, overrides via `setattr`          |
| `target_fail_missing_port`    | FAIL     | Copies only the keys it is given: no defaults on an empty override       |
| `target_fail_stores_password` | FAIL     | `self.__dict__.update(...)` keeps the password                            |

Targets do not carry `__archtest__` metadata; the markers live only on the
reference side.

See `findings.md` for the expected vs observed verdicts.
