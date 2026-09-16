# ENUM001 — `is_enum` showcase

The reference module declares one `is_enum` marker per class. The marker
asserts that the matched target class is an `enum.Enum` (or any subclass:
`IntEnum`, `StrEnum`, `Flag`, …), reachable through normal MRO.

## Marker matrix exercised

| Reference class  | Base class    | Marker      | Notes                                         |
|------------------|---------------|-------------|-----------------------------------------------|
| `Color`          | `Enum`        | `is_enum()` | Plain Enum                                    |
| `Priority`       | `IntEnum`     | `is_enum()` | Subclass of `Enum` via `IntEnum`              |
| `Mode`           | `StrEnum`     | `is_enum()` | Subclass of `Enum` via `StrEnum` (Py 3.11+)   |
| `Permissions`    | `Flag`        | `is_enum()` | Subclass of `Enum` via `Flag`                 |
| `TransitiveEnum` | `_MarkerEnum` | `is_enum()` | Reaches `Enum` transitively through a base    |

All markers use defaults: `severity="error"`, `message=None`. The marker has
no other parameters.

## Parameter matrix

| Parameter  | Type             | Default   | Purpose                          |
|------------|------------------|-----------|----------------------------------|
| `severity` | `"error"`/`"warning"`/`"info"` | `"error"` | Reported severity if the rule fails |
| `message`  | `str \| None`    | `None`    | Optional override message        |

## Target index

| Target                          | Expected | What it isolates                                           |
|---------------------------------|----------|------------------------------------------------------------|
| `target_pass_basic`             | PASS     | All five enum classes verbatim                             |
| `target_pass_int_enum`          | PASS     | `Priority` retained as `IntEnum`                           |
| `target_pass_str_enum`          | PASS     | `Mode` retained as `StrEnum`                               |
| `target_pass_flag_enum`         | PASS     | `Permissions` retained as `Flag`                           |
| `target_pass_transitive_enum`   | PASS     | `TransitiveEnum` reaches `Enum` via `_MarkerEnum`          |
| `target_fail_regular_class`     | FAIL     | `Color` becomes a plain class with constants — not an Enum |

Targets do not carry `__archtest__` metadata; the markers live only on the
reference side.

See `findings.md` (added by the parent run) for the expected vs observed
verdicts.
