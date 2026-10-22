"""Translation between the reference's and the target's names for runtime rules.

A runtime marker names reference modules (``forbid_runtime_calls("repository")``)
and reference classes (``{"$new": "repository.OrderRepository"}``). The target
may put the same entities in modules of other names; the matching step pairs
them, and these tests check that the names follow the pairs.
"""

from __future__ import annotations

from types import SimpleNamespace

from pythonarchtesting.dynamic.translation import NameTranslation
from pythonarchtesting.matching import MatchStatus


def _entity(role: str, module: str, qualname: str, kind: str = "class"):
    return SimpleNamespace(
        canonical_id=f"{role}:{module}:{qualname}",
        module_path=module,
        qualname=qualname,
        kind=kind,
    )


def _context(pairs: list[tuple[tuple[str, str], tuple[str, str] | None]]):
    """``pairs`` of (source module, qualname) -> (target module, qualname)."""
    source_by_id, target_by_id, matches = {}, {}, {}
    for (s_module, s_name), target in pairs:
        source = _entity("source", s_module, s_name)
        source_by_id[source.canonical_id] = source
        if target is None:
            matches[source.canonical_id] = SimpleNamespace(
                status=MatchStatus.UNMATCHED, target_id=None
            )
            continue
        entity = _entity("target", *target)
        target_by_id[entity.canonical_id] = entity
        matches[source.canonical_id] = SimpleNamespace(
            status=MatchStatus.MATCHED, target_id=entity.canonical_id
        )
    return SimpleNamespace(
        source_by_id=source_by_id, target_by_id=target_by_id, matches=matches
    )


_RENAMED = [
    (("repository", "OrderRepository"), ("storage", "OrderRepository")),
    (("repository", "OrderRepository.get"), ("storage", "OrderRepository.get")),
    (("service", "OrderService"), ("service", "OrderService")),
    (("service", "OrderService.place"), ("service", "OrderService.place")),
]


def test_a_call_into_a_renamed_module_is_named_by_the_reference_module() -> None:
    names = NameTranslation.from_context(_context(_RENAMED))

    assert names.source_module("storage", "OrderRepository.get") == "repository"


def test_an_unmatched_function_follows_the_module_of_its_neighbours() -> None:
    names = NameTranslation.from_context(_context(_RENAMED))

    # A helper the reference does not have still lives in the renamed module.
    assert names.source_module("storage", "_helper") == "repository"


def test_a_nested_function_is_named_by_its_enclosing_entity() -> None:
    names = NameTranslation.from_context(_context(_RENAMED))

    assert (
        names.source_module("storage", "OrderRepository.get.<locals>.<lambda>")
        == "repository"
    )


def test_entity_module_is_none_for_code_no_matched_entity_encloses() -> None:
    names = NameTranslation.from_context(_context(_RENAMED))

    assert names.entity_module("storage", "OrderRepository.get") == "repository"
    assert names.entity_module("storage", "_helper") is None


def test_a_module_outside_the_project_keeps_its_name() -> None:
    names = NameTranslation.from_context(_context(_RENAMED))

    assert names.source_module("sqlite3", "connect") == "sqlite3"


def test_entities_of_one_target_module_keep_their_own_reference_modules() -> None:
    # The target put the service and the repository into one module.
    names = NameTranslation.from_context(
        _context(
            [
                (("repository", "OrderRepository"), ("app", "OrderRepository")),
                (("service", "OrderService"), ("app", "OrderService")),
                (("service", "OrderService.place"), ("app", "OrderService.place")),
            ]
        )
    )

    assert names.source_module("app", "OrderRepository.get") == "repository"
    assert names.source_module("app", "OrderService.place") == "service"


def test_a_low_confidence_match_still_names_the_target_module() -> None:
    # A class moved to a renamed module matches with low confidence only.
    ctx = _context(_RENAMED[:2])
    for match in ctx.matches.values():
        match.status = MatchStatus.LOW_CONFIDENCE

    names = NameTranslation.from_context(ctx)

    assert names.source_module("storage", "OrderRepository.get") == "repository"


def test_an_ambiguous_match_is_not_used() -> None:
    ctx = _context(_RENAMED[:2])
    for match in ctx.matches.values():
        match.status = MatchStatus.AMBIGUOUS

    names = NameTranslation.from_context(ctx)

    assert names.source_module("storage", "OrderRepository.get") == "storage"


def test_without_matches_every_name_is_kept() -> None:
    names = NameTranslation.from_context(SimpleNamespace())

    assert names.source_module("storage", "OrderRepository.get") == "storage"
    assert names.target_modules("repository") == ["repository"]


def test_a_declared_module_is_translated_to_the_target_module() -> None:
    names = NameTranslation.from_context(_context(_RENAMED))

    assert names.target_modules("repository") == ["storage"]
    assert names.target_modules("sqlite3") == ["sqlite3"]


def test_a_declared_package_covers_every_target_module_of_its_modules() -> None:
    names = NameTranslation.from_context(
        _context(
            [
                (("infra.repo", "Repo"), ("storage.repo", "Repo")),
                (("infra.cache", "Cache"), ("caching", "Cache")),
            ]
        )
    )

    assert names.target_modules("infra") == ["caching", "infra", "storage.repo"]


def test_a_declared_module_merged_with_another_keeps_its_name() -> None:
    # Forbidding the merged module would forbid the allowed service as well.
    names = NameTranslation.from_context(
        _context(
            [
                (("repository", "OrderRepository"), ("app", "OrderRepository")),
                (("service", "OrderService"), ("app", "OrderService")),
            ]
        )
    )

    assert names.target_modules("repository") == ["repository"]


def test_new_names_a_class_of_a_renamed_module_by_its_target_module() -> None:
    names = NameTranslation.from_context(_context(_RENAMED))
    source = _entity("source", "controller", "handle", "function")
    target = _entity("target", "controller", "handle", "function")
    cases = [
        {
            "args": [
                {"id": "A1"},
                {
                    "$new": "service.OrderService",
                    "args": [{"$new": "repository.OrderRepository"}],
                },
            ]
        }
    ]

    translated = names.cases(cases, source, target)

    assert translated == [
        {
            "args": [
                {"id": "A1"},
                {
                    "$new": "service.OrderService",
                    "args": [{"$new": "storage.OrderRepository"}],
                },
            ]
        }
    ]
    assert cases[0]["args"][1]["args"][0]["$new"] == "repository.OrderRepository"


def test_new_of_a_class_in_the_rule_module_follows_the_matched_class() -> None:
    names = NameTranslation.from_context(
        _context(
            [
                (("service", "OrderService"), ("services", "Service")),
                (("service", "place"), ("services", "place")),
            ]
        )
    )
    source = _entity("source", "service", "place", "function")
    target = _entity("target", "services", "place", "function")

    assert names.value({"$new": "OrderService"}, source, target) == {"$new": "Service"}


def test_new_of_a_class_moved_to_another_module_names_that_module() -> None:
    names = NameTranslation.from_context(
        _context([(("service", "OrderService"), ("domain.services", "Service"))])
    )
    source = _entity("source", "service", "place", "function")
    target = _entity("target", "app", "place", "function")

    assert names.value({"$new": "OrderService"}, source, target) == {
        "$new": "domain.services.Service"
    }


def test_a_step_calls_the_method_the_reference_method_was_matched_to() -> None:
    names = NameTranslation.from_context(
        _context(
            [
                (("cart", "Cart"), ("basket", "Basket")),
                (("cart", "Cart.add_item"), ("basket", "Basket.add")),
                (("cart", "Cart.checkout"), ("basket", "Basket.checkout")),
            ]
        )
    )
    method = _entity("source", "cart", "Cart.checkout", "method")
    target = _entity("target", "basket", "Basket.checkout", "method")
    cls = _entity("source", "cart", "Cart")
    target_cls = _entity("target", "basket", "Basket")
    steps = [{"steps": [{"call": "add_item", "args": [1]}, {"call": "clear"}]}]

    assert names.cases(steps, method, target) == [
        {"steps": [{"call": "add", "args": [1]}, {"call": "clear"}]}
    ]
    assert names.cases(steps, cls, target_cls) == [
        {"steps": [{"call": "add", "args": [1]}, {"call": "clear"}]}
    ]


def test_new_of_an_unknown_name_is_left_alone() -> None:
    names = NameTranslation.from_context(_context(_RENAMED))
    source = _entity("source", "controller", "handle", "function")

    assert names.value({"$new": "collections.OrderedDict"}, source, source) == {
        "$new": "collections.OrderedDict"
    }


_PATTERNS = [
    (("bus", "EventBus"), ("events", "Hub")),
    (("bus", "EventBus.subscribe"), ("events", "Hub.attach")),
    (("bus", "EventBus.publish"), ("events", "Hub.emit")),
    (("config", "Config"), ("config", "Settings")),
    (("config", "Config.instance"), ("config", "Settings.shared")),
    (("config", "get_config"), ("config", "settings")),
]


def test_the_members_a_pattern_rule_calls_take_the_targets_names() -> None:
    names = NameTranslation.from_context(_context(_PATTERNS))
    bus = _entity("source", "bus", "EventBus")
    config = _entity("source", "config", "Config")

    observer = {
        "observer": {
            "subscribe": "subscribe",
            "notify": "publish",
            "unsubscribe": "unsubscribe",
            "notify_args": ["x"],
        }
    }
    assert names.observation(observer, bus) == {
        "observer": {
            "subscribe": "attach",
            "notify": "emit",
            "unsubscribe": "unsubscribe",
            "notify_args": ["x"],
        }
    }
    for access, expected in [("instance", "shared"), ("get_config", "settings")]:
        singleton = {"construct": False, "singleton": {"access": access}}
        assert names.observation(singleton, config)["singleton"] == {"access": expected}
    assert names.observation({"calls": True}, bus) == {"calls": True}
