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

Pattern recipes and copy-ready examples built from these public markers are
documented in [pattern-recipes.md](pattern-recipes.md).

### Placement Summary

| Marker | Purpose | Valid placement |
| --- | --- | --- |
| `required_entity_signature(...)` | Require a compatible function or method signature | Signature-level `Annotated[...]` on parameters or return annotations |
| `required_method(...)` | Require a method with a compatible signature | `__archtest__: Annotated[...]` inside a method body |
| `require_method_set(...)` | Require a set of matching methods on the matched class | Class-level `__archtest__: Annotated[...]` |
| `required_attribute(...)` | Require a class or instance attribute on the matched class | Class-level `__archtest__: Annotated[...]` |
| `required_constructor(...)` | Require a compatible constructor (`__init__` or `__new__`) on the matched class | Class-level `__archtest__: Annotated[...]` |
| `required_factory(...)` | Require a factory method (constructor, classmethod, or staticmethod) on the matched class | `__archtest__: Annotated[...]` inside a factory-capable method body |
| `does_not_have(...)` | Forbid a method, attribute, or property on the matched class | Class-level `__archtest__: Annotated[...]` |
| `forbid_imports(...)` | Forbid imports in a declared scope | `__archtest__: Annotated[...]`, commonly at module level |
| `implements_protocol(...)` | Require structural protocol conformance | Class-level `__archtest__: Annotated[...]` or signature-level `Annotated[...]` |
| `subclass_of(...)` | Require nominal inheritance from a matched base-class counterpart | Class-level `__archtest__: Annotated[...]` |
| `exact_type(...)` | Require the target class to be exactly the matched base-class counterpart | Class-level `__archtest__: Annotated[...]` |
| `not_subclass_of(...)` | Forbid nominal inheritance from a matched base-class counterpart | Class-level `__archtest__: Annotated[...]` |
| `inherits_directly_from(...)` | Require direct nominal inheritance from a matched base-class counterpart | Class-level `__archtest__: Annotated[...]` |
| `is_enum(...)` | Require the matched target class to classify as a stdlib enum-like class | Class-level `__archtest__: Annotated[...]` |
| `is_abstract_class(...)` | Require the matched target class to have unresolved abstract members under the local static model | Class-level `__archtest__: Annotated[...]` |
| `is_concrete_class(...)` | Require the matched target class to have no unresolved abstract members under the local static model | Class-level `__archtest__: Annotated[...]` |
| `is_final_class(...)` | Require the matched target class to be decorated with a recognized `final` decorator | Class-level `__archtest__: Annotated[...]` |
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

### `require_method_set(...)`

Common options:

- `name_match`
- `names`
- `pattern`
- `declared_only`
- `method_kind`
- `min_count`
- `max_count`
- `severity`
- `message`

Notes:

- `require_method_set(...)` is class-level only in v1.
- v1 is methods-only and validates the selected method set by cardinality.
- `name_match="any"` selects all target methods in scope.
- `name_match="regex"` uses `re.fullmatch(pattern, target_method_name)`.
- `name_match="names"` selects target methods whose names are present in `names`.
- `declared_only=False` allows inherited target methods to participate.
- `declared_only=True` counts only methods declared directly on the matched target class.
- `method_kind` accepts `any`, `instance`, `classmethod`, and `staticmethod`.
- `min_count` sets the minimum number of matching methods required.
- `max_count`, when provided, sets the maximum number of matching methods allowed.
- Method kind already has dedicated support through `required_method(..., enforce_method_kind=True)` and `require_method_set(method_kind=...)`; the modifier subset only adds class-level abstract/concrete/final checks.
- v1 does not apply nested per-method rules.
- Public API visibility semantics are out of scope in v1.

Regex example:

```python
from typing import Annotated
from pythonarchtesting.rules import require_method_set


class TestContract:
    __archtest__: Annotated[
        None,
        require_method_set(name_match="regex", pattern=r"test_.*", min_count=1),
    ]
```

Explicit names example:

```python
from typing import Annotated
from pythonarchtesting.rules import require_method_set


class LifecycleContract:
    __archtest__: Annotated[
        None,
        require_method_set(
            name_match="names",
            names=["setUp", "tearDown"],
            min_count=2,
            max_count=2,
        ),
    ]
```

Declared-only example:

```python
from typing import Annotated
from pythonarchtesting.rules import require_method_set


class HandlerContract:
    __archtest__: Annotated[
        None,
        require_method_set(
            name_match="regex",
            pattern=r"handle_.*",
            declared_only=True,
            min_count=1,
        ),
    ]
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
| `allow_missing` | `bool` | `False` | Skip instead of fail when the matched target does not expose the attribute in scope |
| `descriptor_kinds` | `tuple[str, ...] \| None` | `None` | Accept supported non-property descriptors: `"cached_property"` and `"classproperty"` |
| `include_dynamic_attributes` | `bool` | `False` | Opt in to literal `setattr(...)` discovery |
| `interpret_dataclass_fields` | `bool` | `False` | Treat dataclass field declarations as instance attributes |
| `severity` | `str` | `"error"` | Violation severity level |
| `message` | `str \| None` | `None` | Custom violation message |

Notes:

- v1 and v2 both support only class-body `__archtest__: Annotated[...]` declarations.
- Unchanged declarations still compile to `API003/required_attribute/v1`.
- A declaration compiles to `API003/required_attribute/v2` when it uses `descriptor_kinds`, `include_dynamic_attributes=True`, or `interpret_dataclass_fields=True`.
- `storage="any"` accepts either a class attribute or an instance attribute.
- `storage="class"` requires a class-body attribute.
- `storage="instance"` requires an instance attribute discovered from `self.<name> = ...`.
- `allow_property=False` (default): `required_attribute(...)` only accepts concrete attributes unless a v2 descriptor kind is explicitly enabled.
- `allow_property=True`: rule can be satisfied by a `@property` descriptor **or** a concrete attribute.
- `allow_missing=False` (default) keeps the current required-member behavior.
- `allow_missing=True` validates the attribute when present and returns `SKIPPED` only when the matched target does not expose the attribute in the current scope.
- A present but incompatible attribute still fails even when `allow_missing=True`.
- `allow_property=True` is rejected by the compiler when combined with `storage="class"` (properties are instance-facing).
- `require_writable=True` only applies when `allow_property=True` and is ignored otherwise; requires the property to have a `@<name>.setter` method.
- `require_writable=True` also rejects read-only v2 descriptors such as `cached_property` and `classproperty`.
- `declared_only=True` excludes inherited members; `declared_only=False` (default) includes them.
- v1 accepts: concrete attributes (class or instance level) and `@property` descriptors (when `allow_property=True`).
- v1 does NOT accept: ordinary methods, getter-named methods like `get_value()`, `classproperty`, other descriptors, or dynamic `setattr(...)`.
- v2 additionally supports:
  - decorator-based or assignment-based `cached_property`
  - decorator-based or assignment-based `classproperty`
  - dataclass field declarations as instance attributes when `interpret_dataclass_fields=True`
  - literal-name `setattr(self, "name", value)` and `setattr(cls, "NAME", value)` when `include_dynamic_attributes=True`
- Getter-named methods are still not attributes.
- Descriptor detection is static and name-based for the supported patterns only.
- Dynamic detection is literal-only and opt-in; computed names and helper wrappers are ignored.

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

Cached-property requirement (v2):

```python
from typing import Annotated
from pythonarchtesting.rules import required_attribute


class CacheBackedUser:
    __archtest__: Annotated[
        None,
        required_attribute(
            "profile",
            descriptor_kinds=("cached_property",),
        ),
    ]
```

Class-facing descriptor requirement (v2):

```python
from typing import Annotated
from pythonarchtesting.rules import required_attribute


class Settings:
    __archtest__: Annotated[
        None,
        required_attribute(
            "VERSION",
            storage="class",
            descriptor_kinds=("classproperty",),
        ),
    ]
```

Dataclass field as instance attribute (v2):

```python
from typing import Annotated
from pythonarchtesting.rules import required_attribute


class UserContract:
    __archtest__: Annotated[
        None,
        required_attribute(
            "email",
            storage="instance",
            interpret_dataclass_fields=True,
        ),
    ]
```

Dynamic attribute requirement (v2):

```python
from typing import Annotated
from pythonarchtesting.rules import required_attribute


class DynamicTarget:
    __archtest__: Annotated[
        None,
        required_attribute(
            "email",
            storage="instance",
            include_dynamic_attributes=True,
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

Optional attribute requirement (skip if absent, fail if present but incompatible):

```python
from typing import Annotated
from pythonarchtesting.rules import required_attribute


class User:
    __archtest__: Annotated[
        None,
        required_attribute("email", storage="instance", allow_missing=True),
    ]
```

### `required_constructor(...)`

Common options:

- `signature_mode` — `"compatible"` (default), `"exact"`, or `"any"`; compared via the same callable matching model used by `required_method(...)`.
- `constructor_kind` — `"auto"` (default: prefer `__init__`, fall back to `__new__`), `"__init__"`, or `"__new__"`.
- `allow_inherited` — when `True` (default), a constructor inherited from a base class in the target satisfies the rule; when `False`, the constructor must be declared directly on the target class.
- `allow_missing` — when `True`, skip instead of fail when no constructor candidate exists under the current `constructor_kind` / `allow_inherited` scope.
- `severity`
- `message`

Notes:

- Declared `__init__` / `__new__` continue to work as before.
- Statically recognizable dataclass-generated `__init__` is inferred on the
  source side when the source class is decorated with `@dataclass` or
  `@dataclasses.dataclass`, does not declare its own `__init__`, and does not
  disable generation with `init=False`.
- The matched target class also treats a statically recognizable
  dataclass-generated `__init__` as a constructor candidate.
- Factory classmethods and staticmethods are still not part of
  `required_constructor(...)`.
- Metaclass `__call__` is still not inferred.
- Return annotations are not compared.
- Method-kind (regular/classmethod/staticmethod) is not enforced; only the parameter shape is checked (after stripping the `self` / `cls` receiver).
- `signature_mode="any"` requires a constructor candidate to exist under the current `constructor_kind` / `allow_inherited` scope and ignores parameter-shape differences.
- Extra required parameters on the target constructor fail the `compatible` check; extra *optional* parameters are allowed.
- `allow_missing=False` (default) keeps the current required-constructor behavior.
- `allow_missing=True` only skips when no constructor candidate exists in the current scope; a present but incompatible constructor still fails.
- If `constructor_kind="auto"` and the source class has neither a declared
  constructor nor a dataclass-generated `__init__`, the rule is not emitted and
  a compiler evidence item is produced.
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

Example — optional constructor requirement:

```python
from typing import Annotated
from pythonarchtesting.rules import required_constructor


class Plugin:
    __archtest__: Annotated[
        None,
        required_constructor(allow_missing=True),
    ]

    def __init__(self, name: str) -> None:
        self.name = name
```

Example — dataclass-generated constructor contract:

```python
from dataclasses import dataclass
from typing import Annotated
from pythonarchtesting.rules import required_constructor


@dataclass
class User:
    __archtest__: Annotated[None, required_constructor()]
    name: str
    email: str | None = None
```

Example — dataclass target satisfying a constructor rule:

```python
from dataclasses import dataclass


@dataclass
class User:
    name: str
    email: str | None = None
```

### `required_factory(...)`

Common options:

| Option | Type | Default | Purpose |
| --- | --- | --- | --- |
| `signature_mode` | `"compatible" \| "exact" \| "any"` | `"compatible"` | Signature comparison mode |
| `satisfy_with` | `tuple[str, ...]` | `("constructor", "classmethod", "staticmethod")` | Which factory kinds are accepted |
| `allow_inherited` | `bool` | `True` | Allow inherited factory candidates from a base class |
| `name_match` | `"any" \| "exact" \| "alias" \| "regex"` | `"any"` | How the factory candidate name is matched |
| `aliases` | `list[str] \| None` | `None` | Accepted alternative names when `name_match="alias"` |
| `pattern` | `str \| None` | `None` | Regex pattern when `name_match="regex"` |
| `allow_missing` | `bool` | `False` | Skip instead of fail when no accepted factory candidate exists in scope |
| `return_annotation_mode` | `"ignore" \| "compatible" \| "exact"` | `"ignore"` | Optional return-annotation checking for method-backed factories |
| `detection_mode` | `"strict" \| "extended"` | `"strict"` | Factory candidate discovery breadth |
| `severity` | `str` | `"error"` | Violation severity level |
| `message` | `str \| None` | `None` | Custom violation message |

Notes:

- Place `required_factory(...)` on a factory-capable source method only:
  `__init__`, `__new__`, `@classmethod`, or `@staticmethod`.
- `satisfy_with` accepts `"constructor"`, `"classmethod"`, `"staticmethod"`, and `"static_attribute"`.
- `name_match="any"` accepts any matching non-constructor factory name.
- `name_match="exact"` requires the factory name to match the source method name.
- `name_match="alias"` requires `aliases`.
- `name_match="regex"` requires `pattern`.
- `satisfy_with=("static_attribute",)` enables class-body static attribute candidates such as `INSTANCE`, `default`, or `current`.
- Static-attribute candidates require constrained name matching. `name_match="any"` is rejected when `satisfy_with` includes `"static_attribute"`.
- `allow_inherited=True` allows inherited target factory methods to satisfy the rule.
- `allow_inherited=True` also allows inherited class-body static attributes to satisfy the rule.
- `allow_missing=False` (default) keeps the current required-factory behavior.
- `allow_missing=True` only skips when no accepted target factory candidate exists under the current `satisfy_with` / `name_match` / `allow_inherited` scope.
- A present but incompatible accepted candidate still fails even when `allow_missing=True`.
- `signature_mode="any"` requires an accepted factory candidate to exist under the current `satisfy_with` / `name_match` / `allow_inherited` scope and ignores parameter-shape differences.
- Static attributes are treated as zero-parameter providers. Parameterized source factories therefore require `signature_mode="any"` to be satisfied by a static attribute.
- `return_annotation_mode="ignore"` preserves the existing behavior.
- When `return_annotation_mode` is enabled, method-backed factories use callable return annotations and static attributes use the class-body attribute annotation.
- Constructor-backed satisfaction treats the return contract as implicitly satisfied, so constructor candidates still work under return checking.
- `detection_mode="strict"` preserves the current candidate set.
- `detection_mode="extended"` adds conservative support for assignment-based `classmethod(...)` / `staticmethod(...)` definitions and builtin wrapper visibility in decorator stacks.
- Static-attribute support is limited to deterministic class-body assignments and annotations. Dynamic registries, service locators, module-level singletons, post-class assignments, `setattr(...)`, and runtime descriptor behavior are not considered factory candidates.
- The rule is emitted as `API004/required_factory/v1` by default, `API004/required_factory/v2` when `return_annotation_mode != "ignore"` or `detection_mode != "strict"`, and `API004/required_factory/v3` when `satisfy_with` includes `"static_attribute"`.
- When `satisfy_with` includes `"constructor"`, constructor matching reuses the
  same constructor resolution as `required_constructor(...)`, including support
  for statically recognizable dataclass-generated `__init__`.
- Callable rule families now share the same three-way parameter model for parameter comparison: methods, constructors, factories, and negative callable forbids all use `"compatible"`, `"exact"`, and `"any"` where applicable.

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

Return-checked classmethod example:

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
                name_match="exact",
                return_annotation_mode="compatible",
            ),
        ]
        return cls()
```

Exact return-checked staticmethod example:

```python
from typing import Annotated, Self
from pythonarchtesting.rules import required_factory


class Session:
    @staticmethod
    def parse(user_id: str) -> Self:
        __archtest__: Annotated[
            None,
            required_factory(
                satisfy_with=("staticmethod",),
                name_match="exact",
                return_annotation_mode="exact",
            ),
        ]
        return Session(user_id)
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

Static-attribute example:

```python
from typing import Annotated
from pythonarchtesting.rules import required_factory


class Session:
    @classmethod
    def create(cls):
        __archtest__: Annotated[
            None,
            required_factory(
                satisfy_with=("static_attribute",),
                name_match="alias",
                aliases=["INSTANCE", "default", "current"],
                signature_mode="any",
                return_annotation_mode="compatible",
            ),
        ]
        return cls()


class SessionTarget:
    INSTANCE: "SessionTarget"
```

Extended detection example:

```python
from typing import Annotated
from pythonarchtesting.rules import required_factory


class Session:
    @classmethod
    def build(cls, user_id: str):
        __archtest__: Annotated[
            None,
            required_factory(
                satisfy_with=("classmethod",),
                name_match="exact",
                detection_mode="extended",
            ),
        ]
        return cls()


class SessionTarget:
    def _build_impl(cls, user_id: str) -> "SessionTarget":
        return cls()

    build = classmethod(_build_impl)
```

Optional factory example:

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
                allow_missing=True,
            ),
        ]
        return cls()
```

Optional regex example:

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
                name_match="regex",
                pattern="from_.*",
                allow_missing=True,
                detection_mode="extended",
            ),
        ]
        return cls()
```

Example — constructor-backed factory satisfaction on a dataclass target:

```python
from dataclasses import dataclass
from typing import Annotated
from pythonarchtesting.rules import required_factory


class Session:
    def __init__(self, user_id: str):
        __archtest__: Annotated[
            None,
            required_factory(satisfy_with=("constructor",)),
        ]
        self.user_id = user_id


@dataclass
class SessionTarget:
    user_id: str
```

### `does_not_have(...)`

`does_not_have(...)` stays in the existing `NEG001` rule family and now has a
backward-compatible v1/v2 surface.

Options:

| Option | Type | Default | Notes |
| --- | --- | --- | --- |
| `name` | `str \| None` | `None` | Required for `name_match="exact"` unless a method-body declaration derives it from the source method name |
| `member_kind` | `"any" \| "method" \| "attribute" \| "property"` | `"any"` | Filters which member kinds count as forbidden hits |
| `storage` | `"any" \| "instance" \| "class"` | `"any"` | Applies only to attribute hits |
| `declared_only` | `bool` | `False` | Restricts hits to members declared directly on the matched target class |
| `name_match` | `"exact" \| "alias" \| "regex"` | `"exact"` | v2 option for name filtering |
| `aliases` | `list[str] \| None` | `None` | Required when `name_match="alias"` |
| `pattern` | `str \| None` | `None` | Required when `name_match="regex"` |
| `signature_mode` | `"any" \| "compatible" \| "exact"` | `"any"` | v2 option for forbidden method signatures |
| `include_descriptors` | `bool` | `False` | v2 opt-in for descriptor-backed class attributes |
| `include_dynamic_attributes` | `bool` | `False` | v2 opt-in for literal `setattr(self\|cls, "...", ...)` detection |
| `severity` | `"error" \| "warning" \| "info"` | `"error"` | Report severity |
| `message` | `str \| None` | `None` | Override the default report message |

Notes:

- v1 class-body declarations keep the exact-name behavior and still compile to `NEG001/does_not_have/v1`.
- v2 is activated when a v2-only option is used or when `does_not_have(...)` is declared inside a source method body.
- class-body declarations support name-only, alias, and regex absence checks.
- method-body declarations support forbidden methods with optional `signature_mode="compatible"` or `signature_mode="exact"`.
- inherited forbidden members count by default.
- properties remain distinct from attributes unless `member_kind="any"`.
- `storage` still filters only attribute hits.
- dynamic attribute detection is conservative and literal-only: only `setattr(self, "name", value)` and `setattr(cls, "name", value)` are recognized.
- descriptor detection is opt-in and static-only; v2 does not attempt import-time or runtime descriptor resolution.
- import absence remains the responsibility of `forbid_imports(...)`.

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


class Repository:
    __archtest__: Annotated[
        None,
        does_not_have(
            member_kind="method",
            name_match="alias",
            aliases=["debug_dump", "trace_dump"],
        ),
    ]
```

```python
from typing import Annotated
from pythonarchtesting.rules import does_not_have


class Repository:
    __archtest__: Annotated[
        None,
        does_not_have(
            member_kind="method",
            name_match="regex",
            pattern="debug_.+",
        ),
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

```python
from typing import Annotated
from pythonarchtesting.rules import does_not_have


class Repository:
    def debug_dump(self, verbose: bool) -> str:
        __archtest__: Annotated[
            None,
            does_not_have(signature_mode="exact"),
        ]
        return "trace"
```

```python
from typing import Annotated
from pythonarchtesting.rules import does_not_have


class Credentials:
    __archtest__: Annotated[
        None,
        does_not_have(
            "token",
            member_kind="attribute",
            storage="instance",
            include_dynamic_attributes=True,
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

This is a strict subclass check. The target class must inherit from the matched
counterpart of the declared source base either directly or transitively. The
matched base itself does not satisfy the rule.

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

### `exact_type(...)`

Require the matched target class to be exactly the matched target counterpart
of a source base class.

Subclassing does not satisfy this rule. The target must be the counterpart
itself.

Common options:

- `base`
- `severity`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import exact_type


class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[None, exact_type("reference.BaseRepository")]
```

### `not_subclass_of(...)`

Require the matched target class to neither inherit from nor equal the matched
target counterpart of a source base class.

This is the negated form of the nominal subclass rule. Direct subclasses,
transitive subclasses, and the forbidden base counterpart itself all fail.

Common options:

- `base`
- `severity`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import not_subclass_of


class BaseRepository:
    pass


class CsvRepository:
    __archtest__: Annotated[None, not_subclass_of("reference.BaseRepository")]
```

### `inherits_directly_from(...)`

Require the matched target class to list the matched target counterpart of a
source base class among its immediate bases.

Only direct bases are considered. A deeper transitive ancestor does not satisfy
this rule, and the matched base itself does not satisfy it either.

Common options:

- `base`
- `severity`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import inherits_directly_from


class BaseRepository:
    pass


class CsvRepository(BaseRepository):
    __archtest__: Annotated[
        None,
        inherits_directly_from("reference.BaseRepository"),
    ]
```

### `is_enum(...)`

Require the matched target class to classify as enum-like based on stdlib enum
inheritance.

`is_enum(...)` is a dedicated classification rule. It passes when the matched
target class directly inherits from `enum.Enum`, `enum.IntEnum`,
`enum.StrEnum`, `enum.Flag`, or `enum.IntFlag`, or when it inherits from a
local class that is itself enum-like.

It does not treat uppercase constants as enum evidence, and it does not act as
a hidden alias for nominal base matching such as `subclass_of(...)`.

Common options:

- `severity`
- `message`

Examples:

```python
from typing import Annotated
from pythonarchtesting.rules import is_enum


class StatusContract:
    __archtest__: Annotated[None, is_enum()]
```

```python
from enum import Enum


class BaseStatus(Enum):
    OK = "ok"


class DeploymentStatus(BaseStatus):
    READY = "ready"
```

Non-goals in v1:

- No enum-family discriminator parameter
- No support for unresolved third-party enum base classes
- No classification based only on enum-like member names

### `is_abstract_class(...)`

Require the matched target class to classify as abstract under a conservative
local static analysis.

`is_abstract_class(...)` is class-level only. It treats a class as abstract
when it has one or more unresolved abstract member names after combining:

- abstract methods declared on the class
- unresolved abstract member names inherited from local base classes
- concrete overrides declared on the class

Recognized abstract decorators include `abstractmethod`,
`abc.abstractmethod`, and the legacy `abstractclassmethod`,
`abstractstaticmethod`, and `abstractproperty` forms.

This rule uses project-local class resolution only. External abstract base
classes are not expanded into inferred obligations in v1, so the classifier is
conservative by design.

Common options:

- `severity`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import is_abstract_class


class RepositoryContract:
    __archtest__: Annotated[None, is_abstract_class()]
```

### `is_concrete_class(...)`

Require the matched target class to classify as concrete under the same local
static model used by `is_abstract_class(...)`.

`is_concrete_class(...)` passes when the matched class has no unresolved
abstract member names after local-base propagation and concrete overrides are
applied.

Common options:

- `severity`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import is_concrete_class


class RepositoryImplementationContract:
    __archtest__: Annotated[None, is_concrete_class()]
```

### `is_final_class(...)`

Require the matched target class to be decorated with a recognized final-class
decorator.

`is_final_class(...)` is class-level only. Recognized decorators are
`final`, `typing.final`, and `typing_extensions.final` after import alias
normalization where available.

This rule does not infer finality from comments or naming, and method-level
`@final` usage does not satisfy the class rule.

Common options:

- `severity`
- `message`

Example:

```python
from typing import Annotated
from pythonarchtesting.rules import is_final_class


class ValueObjectContract:
    __archtest__: Annotated[None, is_final_class()]
```

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
