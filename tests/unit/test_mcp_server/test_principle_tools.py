from __future__ import annotations

import json

import anyio
import pytest

from pythonarchtesting.mcp_server.errors import ToolInputError
from pythonarchtesting.mcp_server.principles import describe_principle, list_principles


def test_list_principles_gives_one_line_each():
    items = list_principles()
    assert [item["id"] for item in items] == ["encapsulation", "io_separation"]
    for item in items:
        assert set(item) == {"id", "name", "level", "summary"}
        assert "\n" not in item["summary"]
    by_id = {item["id"]: item for item in items}
    assert by_id["io_separation"]["summary"].startswith("Functions that compute")


def test_describe_principle_returns_the_full_entry():
    entry = describe_principle("io_separation")
    assert json.loads(json.dumps(entry)) == entry
    assert set(entry) >= {"id", "name", "summary", "why", "roles", "checks", "errors"}
    errors = {error["id"]: error for error in entry["errors"]}
    assert errors["output_through_helper"]["signature"] == {
        "kind": "call",
        "callee": "builtins:print",
        "via": True,
    }
    assert {"title", "what", "why", "fix", "detected_by"} <= set(
        errors["logic_in_main"]
    )
    assert entry["neutral"][0]["id"] == "model_solution"


def test_describe_unknown_principle_suggests():
    with pytest.raises(ToolInputError, match="did you mean: encapsulation"):
        describe_principle("encapsulaton")


def test_principle_tools_through_the_server():
    pytest.importorskip("mcp")
    from mcp.server.mcpserver.exceptions import ToolError

    from pythonarchtesting.mcp_server import server

    async def listed():
        return await server.mcp.call_tool("list_principles", {})

    async def described(principle_id: str):
        return await server.mcp.call_tool(
            "describe_principle", {"principle_id": principle_id}
        )

    assert "io_separation" in str(anyio.run(listed))
    assert "bypass_method" in str(anyio.run(described, "encapsulation"))
    with pytest.raises(ToolError, match="unknown principle 'nope'"):
        anyio.run(described, "nope")


def test_describe_principle_carries_the_legends():
    entry = describe_principle("io_separation")
    placeholders = entry["placeholders"]
    assert {"function", "callee_short", "via_last"} <= set(placeholders)
    assert all(
        isinstance(meaning, str) and meaning for meaning in placeholders.values()
    )
    assert set(entry["signature_keys"]) == {
        "kind",
        "callee",
        "change",
        "via",
        "private",
    }
    for error in entry["errors"]:
        assert set(error.get("signature", {})) <= set(entry["signature_keys"])
