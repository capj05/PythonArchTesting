# MOD001 — Modifier Markers

Demonstrates the eight Python modifier markers shipped with PythonArchTesting.
Each marker constrains a class- or method-level modifier (abstract / concrete,
final / non-final). Markers carry no payload other than the standard
`severity` and `message` keyword arguments.

## Markers and reference classes

| Marker | Reference class | What it asserts |
|--------|-----------------|-----------------|
| `is_abstract_class()` | `AbstractShape` | Class must be abstract (ABC base or has abstract methods). |
| `is_concrete_class()` | `ConcreteCircle` | Class must be concrete (no abstract methods, not declared abstract). |
| `is_final_class()` | `FinalConfig` | Class must carry `@typing.final`. |
| `is_non_final_class()` | `NonFinalBase` | Class must NOT carry `@typing.final`. |
| `is_abstract_method()` | `WithAbstractMethod.step` | Method must be `@abstractmethod`. |
| `is_non_abstract_method()` | `WithConcreteMethod.step` | Method must NOT be abstract. |
| `is_final_method()` | `WithFinalMethod.step` | Method must carry `@typing.final`. |
| `is_non_final_method()` | `WithNonFinalMethod.step` | Method must NOT carry `@typing.final`. |

## Targets

| Target | Expected | Variation |
|--------|----------|-----------|
| `target_pass_basic` | PASS | All modifiers match the reference verbatim. |
| `target_fail_abstract_class_not_abstract` | FAIL | `AbstractShape` drops `ABC` and abstract methods. |
| `target_fail_concrete_class_is_abstract` | FAIL | `ConcreteCircle` becomes `ABC` with `@abstractmethod`. |
| `target_fail_final_class_not_final` | FAIL | `FinalConfig` loses its `@final` decorator. |
| `target_fail_non_final_class_is_final` | FAIL | `NonFinalBase` is decorated with `@final`. |
| `target_fail_abstract_method_not_abstract` | FAIL | `WithAbstractMethod.step` drops `@abstractmethod` and gains a body. |
| `target_fail_non_abstract_method_is_abstract` | FAIL | `WithConcreteMethod` becomes `ABC` with `@abstractmethod def step`. |
| `target_fail_final_method_not_final` | FAIL | `WithFinalMethod.step` loses `@final`. |
| `target_fail_non_final_method_is_final` | FAIL | `WithNonFinalMethod.step` is decorated with `@final`. |

## Layout

```
mod001_modifiers/
    reference/        rules + class declarations (with __archtest__)
    assignments/      one passing target + eight failing targets
    reports/          CLI output, generated on demand and not checked in
```

## Notes

- One marker per declaration site. Class-level markers go in the class body
  via `__archtest__: Annotated[None, marker()]`; method-level markers go
  inside the method body using the same idiom.
- Targets do not carry any `__archtest__` declarations — the rules live on
  the reference project only and are checked against matched target entities.
