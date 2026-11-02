"""Pairing by name where the scores leave an entity unpaired (``name_fallback``)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from pythonarchtesting.config import load_config
from pythonarchtesting.entities import build_entity_index, sort_entities
from pythonarchtesting.entities_extraction import (
    extract_entities_from_ast_with_nonmatchable,
)
from pythonarchtesting.evidence.collection import parse_python_modules
from pythonarchtesting.matching import MatchingConfig, MatchStatus, run_matching

_REFERENCE = {
    "controller.py": (
        "def handle_order(service, order_id):\n"
        "    if not order_id:\n"
        "        return None\n"
        "    return service.place(order_id)\n"
    ),
    "service.py": (
        "class OrderService:\n"
        "    def __init__(self, repository):\n"
        "        self.repository = repository\n\n"
        "    def place(self, order_id):\n"
        "        return self.repository.save(order_id)\n"
    ),
}
# Renamed modules, other bodies: the scores pair none of it.
_TARGET = {
    "handler.py": (
        "def handle_order(svc, oid):\n"
        "    result = svc.place(oid)\n"
        "    print('placed', oid)\n"
        "    return result\n"
    ),
    "orders.py": (
        "class OrderService:\n"
        "    def __init__(self, repo):\n"
        "        self._repo = repo\n"
        "        self._count = 0\n\n"
        "    def place(self, oid):\n"
        "        self._count += 1\n"
        "        stored = self._repo.save(oid)\n"
        "        return stored\n"
    ),
}


def _index(root: Path, files: dict[str, str], role: str) -> Any:
    root.mkdir(parents=True)
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    config = load_config(config_path=None, cli_args={}, discover_from_cwd=False)
    parsed, _ = parse_python_modules(
        root_path=root, config=config, target_module_name=None
    )
    entities = []
    for module in parsed:
        found, _ = extract_entities_from_ast_with_nonmatchable(
            module.tree,
            module.file_text,
            module.file_path,
            root,
            None,
            role=role,
            include_nested_functions=False,
            root_label=role,
        )
        entities.extend(found)
    return build_entity_index(sort_entities(entities))


def _match(
    tmp_path: Path,
    target: dict[str, str],
    fallback: bool = True,
    reference: dict[str, str] | None = None,
) -> dict[str, tuple[MatchStatus, str | None, list[str]]]:
    source_index = _index(tmp_path / "reference", reference or _REFERENCE, "source")
    target_index = _index(tmp_path / "target", target, "target")
    config = MatchingConfig.from_config(
        load_config(config_path=None, cli_args={}, discover_from_cwd=False)
    )
    _, by_source = run_matching(
        source_index, target_index, replace(config, name_fallback=fallback)
    )
    targets = {e.canonical_id: e for e in target_index.all_sorted}
    found = {}
    for source in source_index.all_sorted:
        match = by_source[source.canonical_id]
        target_entity = targets.get(match.target_id or "")
        found[f"{source.module_path}:{source.qualname}"] = (
            match.status,
            (
                f"{target_entity.module_path}:{target_entity.qualname}"
                if target_entity is not None and match.status == MatchStatus.MATCHED
                else None
            ),
            [reason["code"] for reason in match.reasons],
        )
    return found


def test_without_the_fallback_renamed_modules_stay_unpaired(tmp_path: Path):
    found = _match(tmp_path, _TARGET, fallback=False)

    assert found["controller:handle_order"][0] != MatchStatus.MATCHED


def test_the_only_entity_of_a_name_is_paired(tmp_path: Path):
    found = _match(tmp_path, _TARGET)

    status, target, codes = found["controller:handle_order"]
    assert (status, target) == (MatchStatus.MATCHED, "handler:handle_order")
    assert "unique_name" in codes
    assert found["service:OrderService"][1] == "orders:OrderService"


def test_methods_follow_their_class(tmp_path: Path):
    target = {
        **_TARGET,
        # A second place() elsewhere: the name alone no longer decides.
        "other.py": "class Other:\n    def place(self, x):\n        return x\n",
    }

    found = _match(tmp_path, target)

    status, paired, codes = found["service:OrderService.place"]
    assert (status, paired) == (MatchStatus.MATCHED, "orders:OrderService.place")
    assert "member_of_paired_class" in codes


def test_a_target_that_cannot_take_the_arguments_is_not_paired(tmp_path: Path):
    target = {
        **_TARGET,
        "handler.py": _TARGET["handler.py"].replace(
            "def handle_order(svc, oid):", "def handle_order(svc, oid, extra):"
        ),
    }

    assert _match(tmp_path, target)["controller:handle_order"][1] is None


def test_two_entities_of_the_name_pair_neither(tmp_path: Path):
    target = {**_TARGET, "more.py": "def handle_order(a, b):\n    return a\n"}

    assert _match(tmp_path, target)["controller:handle_order"][1] is None


def test_an_automatic_match_is_kept(tmp_path: Path):
    found = _match(tmp_path, {**_REFERENCE, **_TARGET})

    status, paired, codes = found["controller:handle_order"]
    assert paired == "controller:handle_order"
    assert "unique_name" not in codes


def test_a_method_is_never_paired_by_its_name_alone(tmp_path: Path):
    target = {
        **_TARGET,
        "orders.py": (
            "class _Base:\n"
            "    def place(self, oid):\n"
            "        return oid\n\n\n"
            "class OrderService(_Base):\n"
            "    def __init__(self, repo):\n"
            "        self._repo = repo\n"
        ),
    }

    # The only place() is the base class's, not OrderService's own.
    assert _match(tmp_path, target)["service:OrderService.place"][1] is None


_BODY = (
    "    total = 0\n"
    "    for item in items:\n"
    "        if item.price > 0:\n"
    "            total += item.price * item.qty\n"
    "    return round(total, 2)\n"
)
_TWIN = (
    "    s = 0\n"
    "    for it in items:\n"
    "        if it.price > 0:\n"
    "            s += it.price * it.qty\n"
    "    print(s)\n"
    "    return s\n"
)
_UNRELATED = "def compute(argv):\n    print(argv)\n    return 0\n"


def test_a_weak_score_for_another_target_is_not_overridden(tmp_path: Path):
    found = _match(
        tmp_path,
        {"pricing.py": "def compute_total(items):\n" + _TWIN, "cli.py": _UNRELATED},
        reference={"billing.py": "def compute(items):\n" + _BODY},
    )

    status, _, codes = found["billing:compute"]
    assert status != MatchStatus.MATCHED
    assert "unique_name" not in codes


def test_a_pair_by_name_names_its_target_first_among_the_candidates(tmp_path: Path):
    from dataclasses import replace as _replace

    source_index = _index(tmp_path / "reference", _REFERENCE, "source")
    target_index = _index(tmp_path / "target", _TARGET, "target")
    config = MatchingConfig.from_config(
        load_config(config_path=None, cli_args={}, discover_from_cwd=False)
    )
    _, by_source = run_matching(
        source_index, target_index, _replace(config, name_fallback=True)
    )
    (match,) = [m for k, m in by_source.items() if ":handle_order:" in k]
    assert "unique_name" in [r["code"] for r in match.reasons]
    assert match.candidates[0].target_id == match.target_id
    assert match.confidence == match.candidates[0].confidence


def test_a_class_without_the_reference_methods_is_not_paired(tmp_path: Path):
    user = (
        "class User:\n"
        "    def __init__(self, name, email):\n"
        "        self.name = name\n"
        "        self.email = email\n\n"
        "    def greet(self):\n"
        "        return 'hi ' + self.name\n"
    )
    found = _match(
        tmp_path,
        {
            "domain.py": user.replace("class User", "class Account").replace(
                "'hi '", "'hello '"
            ),
            "errors.py": "class User(Exception):\n    pass\n",
        },
        reference={"domain.py": user},
    )

    assert found["domain:User"][1] != "errors:User"


def test_modules_are_never_paired_by_name(tmp_path: Path):
    found = _match(
        tmp_path,
        {
            "lib/__init__.py": "",
            "lib/helpers.py": "import os\n\n\ndef zzz(q, w):\n    return os.sep\n",
        },
        reference={
            "app/__init__.py": "",
            "app/helpers.py": "def a(x):\n    return x\n",
        },
    )

    # The functions differ in name: only the module could be paired by it.
    assert all("unique_name" not in codes for _, _, codes in found.values())


def test_a_name_two_reference_entities_share_pairs_neither(tmp_path: Path):
    found = _match(
        tmp_path,
        {
            "zz.py": "def load(p):\n"
            "    with open(p) as f:\n"
            "        data = f.read()\n"
            "    return data.strip()\n"
        },
        reference={
            "a.py": "def load(path):\n    return open(path).read()\n",
            "b.py": "def load(path):\n    import json\n    return json.load(open(path))\n",
        },
    )

    assert "unique_name" not in found["a:load"][2]
    assert "unique_name" not in found["b:load"][2]


def test_a_target_another_entity_scores_best_for_is_not_taken(tmp_path: Path):
    found = _match(
        tmp_path,
        {"pricing.py": "def compute_total(items):\n" + _TWIN},
        reference={
            "billing.py": "def compute(items):\n"
            + _BODY
            + "\n\ndef compute_total(order):\n    return sum(order.lines)\n"
        },
    )

    assert "unique_name" not in found["billing:compute_total"][2]


def test_a_property_setter_follows_its_class(tmp_path: Path):
    box = (
        "class Box:\n"
        "    def __init__(self):\n"
        "        self._v = 0\n\n"
        "    @property\n"
        "    def v(self):\n"
        "        return self._v\n\n"
        "    @v.setter\n"
        "    def v(self, value):\n"
        "        self._v = value\n"
    )
    target = (
        "class Box:\n"
        "    def __init__(self):\n"
        "        self.q = 1\n"
        "        self.w = 2\n\n"
        "    @property\n"
        "    def v(self):\n"
        "        print(1)\n"
        "        return self.q + self.w\n\n"
        "    @v.setter\n"
        "    def v(self, value):\n"
        "        print(2)\n"
        "        self.q = value * 2\n"
    )

    source_index = _index(tmp_path / "reference", {"a.py": box}, "source")
    target_index = _index(tmp_path / "target", {"zz.py": target}, "target")
    config = MatchingConfig.from_config(
        load_config(config_path=None, cli_args={}, discover_from_cwd=False)
    )
    _, by_source = run_matching(
        source_index, target_index, replace(config, name_fallback=True)
    )
    setters = [
        by_source[e.canonical_id]
        for e in source_index.all_sorted
        if e.kind == "method" and e.qualname == "Box.v"
    ]
    assert all(m.status == MatchStatus.MATCHED for m in setters)
    assert len({m.target_id for m in setters}) == len(setters)


def test_a_local_class_is_not_paired(tmp_path: Path):
    found = _match(
        tmp_path,
        {
            "graph.py": "def build(edges):\n"
            "    class Node:\n"
            "        def __init__(self, value):\n"
            "            self.v = value\n"
            "    return [Node(e) for e in edges]\n"
        },
        reference={
            "tree.py": "class Node:\n"
            "    def __init__(self, value):\n"
            "        self.value = value\n"
        },
    )

    assert "unique_name" not in found["tree:Node"][2]


def test_inside_a_paired_class_the_name_beats_a_weak_guess(tmp_path: Path):
    store = (
        "class Store:\n"
        "    def __init__(self):\n"
        "        self.items = {}\n\n"
        "    def add(self, key, item):\n"
        "        self.items[key] = item\n\n"
        "    def find(self, key):\n"
        "        return self.items.get(key)\n"
    )
    target = (
        "class Store:\n"
        "    def __init__(self):\n"
        "        self._data = []\n\n"
        "    def add(self, key, item):\n"
        "        self._data.append((key, item))\n"
        "        print('added', key)\n\n"
        "    def find(self, key):\n"
        "        for k, v in self._data:\n"
        "            if k == key:\n"
        "                return v\n"
        "        return None\n"
    )

    found = _match(tmp_path, {"persistence.py": target}, reference={"memory.py": store})

    assert found["memory:Store.add"][1] == "persistence:Store.add"
    assert found["memory:Store.find"][1] == "persistence:Store.find"


# A reference bus (program 3) and a student's (E2): in a subpackage the
# target's subscribe scores as well for the reference's unsubscribe as for
# its subscribe.
_BUS = (
    '"""A synchronous event bus: every subscriber of an event\'s name, in order."""\n'
    "\n"
    "from __future__ import annotations\n"
    "\n"
    "from typing import Any, Callable\n"
    "\n"
    "Handler = Callable[[Any], None]\n"
    "\n"
    "\n"
    "class EventBus:\n"
    "    def __init__(self) -> None:\n"
    "        self._handlers: dict[str, list[Handler]] = {}\n"
    "\n"
    "    def subscribe(self, name: str, handler: Handler) -> None:\n"
    "        self._handlers.setdefault(name, []).append(handler)\n"
    "\n"
    "    def unsubscribe(self, name: str, handler: Handler) -> None:\n"
    "        self._handlers.get(name, []).remove(handler)\n"
    "\n"
    "    def publish(self, event: Any) -> None:\n"
    "        for handler in list(self._handlers.get(event.name, [])):\n"
    "            handler(event)\n"
)
_BUS_TARGET = (
    '"""A small synchronous publish/subscribe bus keyed by event name."""\n'
    "\n"
    "from typing import Callable, Dict, List\n"
    "\n"
    "\n"
    "class EventBus:\n"
    "    def __init__(self):\n"
    "        self._handlers: Dict[str, List[Callable]] = {}\n"
    "\n"
    "    def subscribe(self, name: str, handler: Callable) -> None:\n"
    "        self._handlers.setdefault(name, []).append(handler)\n"
    "\n"
    "    def unsubscribe(self, name: str, handler: Callable) -> None:\n"
    "        handlers = self._handlers.get(name, [])\n"
    "        if handler in handlers:\n"
    "            handlers.remove(handler)\n"
    "\n"
    "    def publish(self, event) -> None:\n"
    "        for handler in list(self._handlers.get(event.name, ())):\n"
    "            handler(event)\n"
)


def test_two_reference_entities_never_share_a_matched_target(tmp_path: Path):
    found = _match(
        tmp_path,
        {
            "__init__.py": "",
            "application/__init__.py": "",
            "application/event_bus.py": _BUS_TARGET,
        },
        reference={
            "__init__.py": "",
            "application/__init__.py": "",
            "application/bus.py": _BUS,
        },
    )

    matched = [
        target
        for status, target, _ in found.values()
        if status == MatchStatus.MATCHED and target is not None
    ]
    assert len(matched) == len(set(matched))
    assert found["application.bus:EventBus.subscribe"][1] == (
        "application.event_bus:EventBus.subscribe"
    )
    assert found["application.bus:EventBus.unsubscribe"][1] == (
        "application.event_bus:EventBus.unsubscribe"
    )


def test_a_dataclass_is_paired_although_its_init_is_generated(tmp_path: Path):
    reference = {
        "__init__.py": "",
        "patients.py": (
            "class Patient:\n"
            "    def __init__(self, patient_id, name):\n"
            "        self.patient_id = patient_id\n"
            "        self.name = name\n\n"
            "    def greeting(self):\n"
            "        return 'Dear ' + self.name\n"
        ),
    }
    target = {
        "__init__.py": "",
        "person.py": (
            "from dataclasses import dataclass\n\n\n"
            "@dataclass\n"
            "class Patient:\n"
            "    patient_id: str\n"
            "    name: str\n\n"
            "    def greeting(self):\n"
            "        return f'Dear {self.name}'\n"
        ),
    }

    found = _match(tmp_path, target, reference=reference)

    assert found["patients:Patient"][:2] == (MatchStatus.MATCHED, "person:Patient")
