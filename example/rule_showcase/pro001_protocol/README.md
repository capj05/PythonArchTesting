# PRO001 — implements_protocol marker showcase

Reference module declares one `implements_protocol(...)` marker per class so
each target isolates a single tunable: signature compatibility mode, return-
annotation strictness, or method-kind enforcement.

The four protocols are defined in `reference/protocols.py` and re-declared
verbatim in every target's `protocols.py` (targets carry no `__archtest__`
markers). Only `services.py` differs across targets.

## Protocols

| Protocol       | Members                                            |
|----------------|----------------------------------------------------|
| `Storage`      | `save(self, key: str, value: bytes) -> None`, `load(self, key: str) -> bytes` |
| `Counter`      | `increment(self) -> int`                           |
| `Builder`      | `@classmethod create(cls) -> "Builder"`            |
| `StrictReader` | `read(self, path: str) -> str`                     |

## Marker matrix exercised

| Reference class | Protocol       | Tuned parameter                       | What it isolates                                                          |
|-----------------|----------------|---------------------------------------|---------------------------------------------------------------------------|
| `FileStorage`   | `Storage`      | `signature_mode="compatible"`         | Extra defaulted kwargs are accepted; missing methods still fail           |
| `TickCounter`   | `Counter`      | `return_annotation="error"`           | Mismatched return annotation escalates from warning to hard failure       |
| `WidgetBuilder` | `Builder`      | `enforce_method_kind=True`            | Method kind (`@classmethod`) must match the protocol declaration          |
| `TextReader`    | `StrictReader` | `signature_mode="exact"`              | Signature must match byte-for-byte — no extra parameters, even defaulted  |

All markers use default `severity="error"` and no custom `message`.

## Target index

| Target                                  | Expected | What it exercises                                                                                  |
|-----------------------------------------|----------|----------------------------------------------------------------------------------------------------|
| `target_pass_basic`                     | PASS     | Verbatim copies of all four classes                                                                |
| `target_pass_compatible_extra_param`    | PASS     | `FileStorage.save` adds `*, ttl: int = 0` — accepted under `signature_mode="compatible"`           |
| `target_fail_missing_method`            | FAIL     | `FileStorage` drops `load` — missing required protocol member                                      |
| `target_fail_wrong_return`              | FAIL     | `TickCounter.increment` returns `str` instead of `int` — `return_annotation="error"` escalates     |
| `target_fail_method_kind`               | FAIL     | `WidgetBuilder.create` is a regular instance method — fails `enforce_method_kind=True`             |
| `target_fail_exact_signature`           | FAIL     | `TextReader.read` adds an extra defaulted param — rejected by `signature_mode="exact"`             |

## How to re-run

```bash
python-arch-test --validate-declarations \
    --source example/rule_showcase/pro001_protocol/reference

for t in target_pass_basic target_pass_compatible_extra_param \
         target_fail_missing_method target_fail_wrong_return \
         target_fail_method_kind target_fail_exact_signature; do
  python-arch-test \
      --source example/rule_showcase/pro001_protocol/reference \
      --target example/rule_showcase/pro001_protocol/assignments/$t \
      --format json \
      --output example/rule_showcase/pro001_protocol/reports/$t.report.json
done
```

See `findings.md` (added by the parent run) for the expected/observed verdict cross-check.
