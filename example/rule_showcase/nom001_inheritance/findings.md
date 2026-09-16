# NOM001 — findings

## Expected vs. observed

| Target                                | Expected | Observed              | Status |
|---------------------------------------|----------|-----------------------|--------|
| `target_pass_basic`                   | PASS     | exit=0, 4 OK          | OK     |
| `target_pass_transitive_subclass`     | PASS     | exit=0, 4 OK          | OK     |
| `target_fail_subclass_required`       | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |
| `target_fail_not_subclass_violated`   | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |
| `target_fail_direct_inherit_violated` | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |
| `target_fail_exact_type_violated`     | FAIL     | exit=1, 3 OK / 1 FAIL | OK     |

## Capabilities exercised

- `subclass_of("Animal")` — accepts direct and transitive subclasses.
- `not_subclass_of("Animal")` — accepts unrelated types, fails on subclasses.
- `inherits_directly_from("Bird")` — fails when target inserts an
  intermediate parent.
- `exact_type("StandaloneType")` — passes only when the target class is
  the same class (not a subclass / alias).

## Limitations / gotchas

### `exact_type` semantics — entity identity, not name

`exact_type("X")` declared on a class `Y` cannot pass: the rule resolves
"X" to the matched target counterpart of source-class X, then compares
that to the matched target counterpart of `Y`. Unless `Y` *is* the source
class named "X", the entities differ and the rule fails.

The practical use of `exact_type` is therefore: "the target class with my
name must equal the target class with this base name", i.e. attach
`exact_type("Self")` to `class Self` to forbid subclass substitution in
the target. Attaching `exact_type` to a class that inherits from the
named base (a common first-time misuse) is always FAILED.

### Base names must be strings, not type objects

Passing a Python `type` instead of a string emits
`compiler_invalid_base_reference` and the rule is dropped. The compiler
expects a qualified or bare name (e.g. `"Animal"`,
`"package.module.Animal"`).

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
