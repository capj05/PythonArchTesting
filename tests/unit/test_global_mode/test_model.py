"""The data of global mode written as JSON and read back."""

from __future__ import annotations

import json

from pythonarchtesting.global_mode.model import BoundEntity, RoleDiscovery


def test_role_discovery_round_trips_through_json() -> None:
    discovery = RoleDiscovery(
        principle="encapsulation",
        roles={
            "owner": (BoundEntity("ship.Cargo", "code", "list in __init__"),),
            "client": (
                BoundEntity("actions", "code", "writes cargo"),
                BoundEntity("ui", "ai", "the game", disputed="only prints"),
            ),
        },
        conflicts=("ui fits more than one role: client, owner",),
        not_applied=None,
    )

    data = json.loads(json.dumps(discovery.to_dict()))

    assert RoleDiscovery.from_dict(data) == discovery


def test_not_applied_discovery_round_trips() -> None:
    discovery = RoleDiscovery("polymorphism", {"base": ()}, (), "base not found")

    assert RoleDiscovery.from_dict(discovery.to_dict()) == discovery
