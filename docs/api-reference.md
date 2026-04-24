# API Reference

## Supported Public API

The supported module entrypoints are:

- `pythonarchtesting.state`
- `pythonarchtesting.runner`

Supported symbols under `pythonarchtesting.state`:

- `ValidationStatus`
- `ValidationResult`
- `rule_result_to_validation`
- `MemoryManager`
- `ModuleDiscovery`
- `ProjectState`

Supported symbols under `pythonarchtesting.runner`:

- `prepare_source`
- `evaluate_target`
- `run_projects`

Deep import paths and historical compatibility aliases are not part of the
supported public API.

## CLI Entrypoints

- `python-arch-test`: preferred installed-package command for most users
- `python -m pythonarchtesting.cli`: developer-oriented module entrypoint for source checkouts

## CLI Flags

- `--config`
- `--source`
- `--target`
- `--targets`
- `--targets-dir`
- `--reference-modules`
- `--project-pattern`
- `--exclude-patterns`
- `--format {json,markdown}`
- `--output`
- `--validate-declarations`
- `--validation-scope {all,logical-views}`

## Supported Annotation Containers

The declaration reader supports:

- `Annotated`
- `typing.Annotated`
- `typing_extensions.Annotated`

Strict tuple metadata also remains supported as a compatibility form:

```python
("required_entity_signature", {"mode": "compatible"})
```

## Marker Factories From `pythonarchtesting.rules`

### Placement Summary

| Marker | Purpose | Valid placement |
| --- | --- | --- |
| `required_entity_signature(...)` | Require a compatible function or method signature | Signature-level `Annotated[...]` on parameters or return annotations |
| `required_method(...)` | Require a method with a compatible signature | `__archtest__: Annotated[...]` inside a method body |
| `required_attribute(...)` | Require a class or instance attribute on the matched class | Class-level `__archtest__: Annotated[...]` |
| `required_constructor(...)` | Require a compatible constructor (`__init__` or `__new__`) on the matched class | Class-level `__archtest__: Annotated[...]` |
| `required_factory(...)` | Require a factory method (constructor, classmethod, or staticmethod) on the matched class | `__archtest__: Annotated[...]` inside a factory-capable method body |
| `does_not_have(...)` | Forbid a method, attribute, or property on the matched class | Class-level `__archtest__: Annotated[...]` |
| `forbid_imports(...)` | Forbid imports in a declared scope | `__archtest__: Annotated[...]`, commonly at module level |
| `implements_protocol(...)` | Require structural protocol conformance | Class-level `__archtest__: Annotated[...]` or signature-level `Annotated[...]` |
| `subclass_of(...)` | Require nominal inheritance from a matched base-class counterpart | Class-level `__archtest__: Annotated[...]` |
| `flow(...)` | Mark a statement as a named flow stage | Statement-level `__archtest__: Annotated[...]` immediately after the statement |
| `enforce_flow(...)` | Require ordered flow stages for a variable | `__archtest__: Annotated[...]` in a function or method body |

### `required_entity_signature(...)`

Common options:

- `mode`
- `allow_extra_params`
- `allow_param_rename`
- `return_annotation`
- `severity`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import required_entity_signature


def normalize(
    value: str,
) -> Annotated[
    str,
    required_entity_signature(mode="compatible", return_annotation="warning"),
]:
    return value.strip()
```

### `required_method(...)`

Common options:

- `signature_mode`
- `enforce_method_kind`
- `allow_missing`
- `declared_only`
- `name_match`
- `aliases`
- `pattern`
- `severity`
- `message`

Notes:

- `signature_mode="compatible"` (default) checks parameter compatibility.
- `signature_mode="exact"` requires the same normalized parameter shape.
- `signature_mode="any"` requires the method to exist but ignores parameter
  names, arity, and `*args` / `**kwargs` differences.
- `allow_missing=False` (default) keeps the current required-member behavior.
- `allow_missing=True` validates the method when present and returns `SKIPPED`
  instead of `FAILED` when the matched target class does not provide the method.
- `declared_only=False` allows an inherited target method to satisfy the rule.
- `declared_only=True` requires the method to be declared directly on the
  matched target class.
- `name_match="exact"` preserves the default same-name lookup.
- `name_match="alias"` allows the source method name or any value from
  `aliases`.
- `name_match="regex"` uses `re.fullmatch(pattern, target_method_name)`.
- `name_match="any"` removes the method-name constraint and looks for any
  compatible method on the matched target class.
- Async/sync compatibility is still enforced for all signature modes.
- `enforce_method_kind=True` still requires instance/class/static parity even
  when `signature_mode="any"`.

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import required_method


class Calculator:
    def add(self, a: int, b: int) -> int:
        __archtest__: Annotated[
            None,
            required_method(
                signature_mode="compatible",
                declared_only=True,
            ),
        ]
        return a + b
```

Optional example:

```python
from typing import Annotated
from pythonarchtesting.rules import required_method


class Repository:
    def find(self, item_id: str) -> str:
        __archtest__: Annotated[
            None,
            required_method(
                signature_mode="compatible",
                allow_missing=True,
            ),
        ]
        return item_id
```

Alias example:

```python
from typing import Annotated
from pythonarchtesting.rules import required_method


class Repository:
    def fetch(self, item_id: str) -> str:
        __archtest__: Annotated[
            None,
            required_method(
                signature_mode="compatible",
                name_match="alias",
                aliases=["get", "load"],
            ),
        ]
        return item_id
```

Regex example:

```python
from typing import Annotated
from pythonarchtesting.rules import required_method


class Repository:
    def fetch(self, item_id: str) -> str:
        __archtest__: Annotated[
            None,
            required_method(
                name_match="regex",
                pattern="(fetch|get)_[a-z]+",
            ),
        ]
        return item_id
```

Any-name example:

```python
from typing import Annotated
from pythonarchtesting.rules import required_method


class Repository:
    def fetch(self, item_id: str) -> str:
        __archtest__: Annotated[
            None,
            required_method(name_match="any"),
        ]
        return item_id
```

Any-params example:

```python
from typing import Annotated
from pythonarchtesting.rules import required_method


class Repository:
    def load(self, item_id: str) -> object:
        __archtest__: Annotated[
            None,
            required_method(signature_mode="any"),
        ]
        return object()
```

### `required_attribute(...)`

Common options:

| Option | Type | Default | Purpose |
| --- | --- | --- | --- |
| `name` | `str` | (required) | Attribute name to check |
| `annotation` | `str \| None` | `None` | Expected type annotation |
| `storage` | `"any" \| "class" \| "instance"` | `"any"` | Where the attribute should be stored |
| `allow_property` | `bool` | `False` | Accept `@property` descriptor as satisfying the rule |
| `require_writable` | `bool` | `False` | Require property to have a setter (only checked when `allow_property=True`) |
| `declared_only` | `bool` | `False` | Exclude inherited members |
| `severity` | `str` | `"error"` | Violation severity level |
| `message` | `str \| None` | `None` | Custom violation message |

Notes:

- v1 supports only class-body `__archtest__: Annotated[...]` declarations.
- `storage="any"` accepts either a class attribute or an instance attribute.
- `storage="class"` requires a class-body attribute.
- `storage="instance"` requires an instance attribute discovered from `self.<name> = ...`.
- `allow_property=False` (default): `required_attribute(...)` only accepts concrete attributes (class or instance).
- `allow_property=True`: rule can be satisfied by a `@property` descriptor **or** a concrete attribute.
- `allow_property=True` is rejected by the compiler when combined with `storage="class"` (properties are instance-facing).
- `require_writable=True` only applies when `allow_property=True` and is ignored otherwise; requires the property to have a `@<name>.setter` method.
- `declared_only=True` excludes inherited members; `declared_only=False` (default) includes them.
- The rule accepts: concrete attributes (class or instance level) and `@property` descriptors (when `allow_property=True`).
- The rule does NOT accept: ordinary methods, getter-named methods like `get_value()`, `classproperty`, or any other descriptor.
- dynamic `setattr(...)` detection is not supported in v1.

Examples:

Plain attribute requirement (existing behavior):

```python
from typing import Annotated
from pythonarchtesting.rules import required_attribute


class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", annotation="str", storage="instance"),
    ]
```

Class-level attribute requirement:

```python
from typing import Annotated
from pythonarchtesting.rules import required_attribute


class Settings:
    __archtest__: Annotated[
        None,
        required_attribute("VERSION", annotation="str", storage="class"),
    ]
```

Property-or-attribute requirement:

```python
from typing import Annotated
from pythonarchtesting.rules import required_attribute


class Config:
    __archtest__: Annotated[
        None,
        required_attribute("value", allow_property=True),
    ]
```

Writable-property requirement (property with setter):

```python
from typing import Annotated
from pythonarchtesting.rules import required_attribute


class Container:
    __archtest__: Annotated[
        None,
        required_attribute(
            "value",
            allow_property=True,
            require_writable=True,
        ),
    ]
```

Declared-only requirement (no inherited members):

```python
from typing import Annotated
from pythonarchtesting.rules import required_attribute


class Service:
    __archtest__: Annotated[
        None,
        required_attribute("name", declared_only=True),
    ]
```

### `required_constructor(...)`

Common options:

- `signature_mode` — `"compatible"` (default) or `"exact"`; compared via the same signature check used by `required_method(...)`.
- `constructor_kind` — `"auto"` (default: prefer `__init__`, fall back to `__new__`), `"__init__"`, or `"__new__"`.
- `allow_inherited` — when `True` (default), a constructor inherited from a base class in the target satisfies the rule; when `False`, the constructor must be declared directly on the target class.
- `severity`
- `message`

Notes:

- v1 only matches declared `__init__` / `__new__` on the source class. Factory classmethods, staticmethods, metaclass `__call__`, and dataclass-generated `__init__` are not inferred.
- Return annotations are not compared.
- Method-kind (regular/classmethod/staticmethod) is not enforced; only the parameter shape is checked (after stripping the `self` / `cls` receiver).
- Extra required parameters on the target constructor fail the `compatible` check; extra *optional* parameters are allowed.
- If `constructor_kind="auto"` and neither `__init__` nor `__new__` is declared on the source class, the rule is not emitted and a compiler evidence item is produced.
- Placement is class-level only; a non-class placement emits `compiler_invalid_target` evidence.

Example — reference with a constructor contract:

```python
from typing import Annotated
from pythonarchtesting.rules import required_constructor


class User:
    __archtest__: Annotated[None, required_constructor()]

    def __init__(self, name: str) -> None:
        self.name = name
```

Example — require the constructor be declared directly on the target class:

```python
from typing import Annotated
from pythonarchtesting.rules import required_constructor


class Session:
    __archtest__: Annotated[
        None,
        required_constructor(allow_inherited=False),
    ]

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
```

### `required_factory(...)`

Common options:

| Option | Type | Default | Purpose |
| --- | --- | --- | --- |
| `signature_mode` | `"compatible" \| "exact"` | `"compatible"` | Signature comparison mode |
| `satisfy_with` | `tuple[str, ...]` | `("constructor", "classmethod", "staticmethod")` | Which factory kinds are accepted |
| `allow_inherited` | `bool` | `True` | Allow factory methods inherited from a base class |
| `name_match` | `"any" \| "exact" \| "alias" \| "regex"` | `"any"` | How the factory method name is matched |
| `aliases` | `list[str] \| None` | `None` | Accepted alternative names when `name_match="alias"` |
| `pattern` | `str \| None` | `None` | Regex pattern when `name_match="regex"` |
| `severity` | `str` | `"error"` | Violation severity level |
| `message` | `str \| None` | `None` | Custom violation message |

Notes:

- Place `required_factory(...)` on a factory-capable source method only:
  `__init__`, `__new__`, `@classmethod`, or `@staticmethod`.
- `satisfy_with` accepts `"constructor"`, `"classmethod"`, and `"staticmethod"`.
- `name_match="any"` accepts any matching non-constructor factory name.
- `name_match="exact"` requires the factory name to match the source method name.
- `name_match="alias"` requires `aliases`.
- `name_match="regex"` requires `pattern`.
- `allow_inherited=True` allows inherited target factory methods to satisfy the rule.
- The rule is emitted as `API004/required_factory/v1`.
- Return annotations are not compared.

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import required_factory


class UserService:
    def __init__(self, name: str, value: int):
        __archtest__: Annotated[None, required_factory()]
        self.name = name
        self.value = value
```

Alias example:

```python
from typing import Annotated
from pythonarchtesting.rules import required_factory


class Session:
    @classmethod
    def create(cls, user_id: str) -> "Session":
        __archtest__: Annotated[
            None,
            required_factory(
                satisfy_with=("classmethod",),
                name_match="alias",
                aliases=["build", "from_user_id"],
            ),
        ]
        return cls()
```

### `does_not_have(...)`

Common options:

- `name`
- `member_kind`
- `storage`
- `declared_only`
- `severity`
- `message`

Notes:

- v1 supports only class-body `__archtest__: Annotated[...]` declarations.
- `member_kind` accepts `any`, `method`, `attribute`, or `property`.
- `storage` accepts `any`, `instance`, or `class` and only filters attribute hits.
- inherited forbidden members count by default.
- `declared_only=True` restricts the check to members declared directly on the matched target class.
- properties are distinct from attributes unless `member_kind="any"`.
- import absence remains the responsibility of `forbid_imports(...)`.
- dynamic `setattr(...)`, regex matching, aliases, and signature-sensitive forbidden method checks are not supported in v1.

Examples:

```python
from typing import Annotated
from pythonarchtesting.rules import does_not_have


class Repository:
    __archtest__: Annotated[
        None,
        does_not_have("debug_dump", member_kind="method"),
    ]
```

```python
from typing import Annotated
from pythonarchtesting.rules import does_not_have


class Credentials:
    __archtest__: Annotated[
        None,
        does_not_have(
            "password",
            member_kind="attribute",
            storage="instance",
            declared_only=True,
        ),
    ]
```

### `forbid_imports(...)`

Common options:

- `scope`
- `package`
- `mode`
- `ignore_type_checking`
- `allow`
- `ignore_globs`
- `severity`
- `message`

Notes:

- `scope="module"` checks the matched target module.
- `scope="package"` checks the configured package subtree.
- `scope="entity"` is accepted as a backward-compatible alias for `module`.
- bare `forbid_imports(...)` defaults to `mode="reachable"`.
- `mode="reachable"` enables graph-based reachable-import analysis.
- `mode="direct"` performs the direct AST import check when requested explicitly.

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import forbid_imports

__archtest__: Annotated[
    None,
    forbid_imports(
        "statistics",
        scope="package",
        package="data_processor",
        mode="direct",
    ),
]
```

### `implements_protocol(...)`

Common options:

- `protocol`
- `signature_mode`
- `enforce_method_kind`
- `return_annotation`
- `severity`
- `message`

Examples:

```python
from typing import Annotated
from pythonarchtesting.rules import implements_protocol


class RepositoryAdapter:
    __archtest__: Annotated[None, implements_protocol("reference.Repository")]
```

```python
from typing import Annotated
from pythonarchtesting.rules import implements_protocol


def build(
    repo: Annotated[object, implements_protocol("reference.Repository")],
) -> Annotated[object, implements_protocol("reference.Repository")]:
    return repo
```

### `subclass_of(...)`

Require the matched target class to inherit from the matched target counterpart
of a source base class.

Common options:

- `base`
- `severity`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import subclass_of


class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, subclass_of("reference.BaseRepository")]
```

V1 limitations:

- Source-reference classes only.
- Class-level declarations only.
- No exact-type mode.
- No signature-level parameter or return nominal checks.

### `flow(...)`

Common options:

- `stage`
- `variable`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import flow


def process(value: str) -> str:
    cleaned = value.strip()
    __archtest__: Annotated[None, flow("cleaned", variable="cleaned")]
    return cleaned
```

### `enforce_flow(...)`

Common options:

- `stages`
- `variable`
- `severity`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import enforce_flow, flow


def process(value: str) -> str:
    value = value.strip()
    __archtest__: Annotated[None, flow("raw", variable="value")]
    value = value.lower()
    __archtest__: Annotated[None, flow("normalized", variable="value")]
    __archtest__: Annotated[
        None,
        enforce_flow(["raw", "normalized"], variable="value"),
    ]
    return value
```

## Placement Rules

- Signature-level declarations are supported for
  `required_entity_signature` and `implements_protocol`.
- Use `__archtest__: Annotated[...]` for module, class, and body declarations.
- `flow(...)` must appear immediately after the statement it annotates.
- Signature and body declarations on the same entity are tracked separately.
- Invalid declarations remain non-fatal in normal analysis and are reported as
  compiler evidence.
- `--validate-declarations` is the focused source-only check for declaration
  authoring and CI.

## Stub-Only Reference Trees

Declaration-only reference trees are supported with `.pyi` files when discovery
is configured with:

```ini
[discovery]
included_file_patterns = *.pyi
```

Mixed `.py` and `.pyi` siblings for the same reference module are not merged.
