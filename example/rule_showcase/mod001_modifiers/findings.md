# MOD001 — findings

## Expected vs. observed

| Target                                      | Expected | Observed              | Status |
|---------------------------------------------|----------|-----------------------|--------|
| `target_pass_basic`                         | PASS     | exit=0, 8 OK          | OK     |
| `target_fail_abstract_class_not_abstract`   | FAIL     | exit=1, 7 OK / 1 FAIL | OK     |
| `target_fail_concrete_class_is_abstract`    | FAIL     | exit=1, 7 OK / 1 FAIL | OK     |
| `target_fail_final_class_not_final`         | FAIL     | exit=1, 7 OK / 1 FAIL | OK     |
| `target_fail_non_final_class_is_final`      | FAIL     | exit=1, 7 OK / 1 FAIL | OK     |
| `target_fail_abstract_method_not_abstract`  | FAIL     | exit=1, 7 OK / 1 FAIL | OK     |
| `target_fail_non_abstract_method_is_abstract` | FAIL   | exit=1, 7 OK / 1 FAIL | OK     |
| `target_fail_final_method_not_final`        | FAIL     | exit=1, 7 OK / 1 FAIL | OK     |
| `target_fail_non_final_method_is_final`     | FAIL     | exit=1, 7 OK / 1 FAIL | OK     |

## Capabilities exercised

Class-level modifiers:

- `is_abstract_class` — succeeds when the class has at least one
  `@abstractmethod` (and conventionally inherits `ABC`).
- `is_concrete_class` — succeeds when no abstract methods remain
  (overridden in a subclass).
- `is_final_class` — succeeds when the class is decorated with
  `typing.final`.
- `is_non_final_class` — succeeds for classes without `@final`.

Method-level modifiers:

- `is_abstract_method` / `is_non_abstract_method` — pair detects the
  presence/absence of `@abstractmethod`.
- `is_final_method` / `is_non_final_method` — pair detects
  `typing.final` on methods (including the class-decorator interplay
  surrounding `@final`).

The matrix isolates each negative variant onto its own target so that a
single modifier mismatch produces exactly one FAIL while leaving the
other 7 modifier rules green — confirming each rule keys off only its
specific modifier predicate.

## Limitations / gotchas

- `is_final_class` requires `@typing.final` (or `@final` from
  `typing_extensions`). Python provides no other way to mark a class
  final, so this is the only signal recognized.
- `is_abstract_method` is detected via `@abc.abstractmethod` only;
  raising `NotImplementedError` in the body is **not** treated as
  abstract.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
