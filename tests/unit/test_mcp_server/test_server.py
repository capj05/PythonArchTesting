from __future__ import annotations

import subprocess
import sys

import anyio
import pytest

pytest.importorskip("mcp")

from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402

from pythonarchtesting.mcp_server import server  # noqa: E402

TOOL_NAMES = {
    "list_markers",
    "describe_marker",
    "validate_declarations",
    "run_evaluation",
    "summarize_report",
    "explain_target",
    "explain_rule",
    "check_cases",
    "verify_marker",
    "propose_mapping",
    "check_architecture",
    "describe_architecture",
    "list_principles",
    "describe_principle",
    "class_overview",
    "prepare_task",
    "discover_roles",
    "prepare_global_task",
    "run_global_evaluation",
}
# Tools that run reference or target code; every other tool only reads.
RUNNING = {
    "run_evaluation",
    "prepare_task",
    "check_cases",
    "verify_marker",
    "check_architecture",
    # Runs the reference's cases in mode="full".
    "describe_architecture",
    # Global mode: writes the self-task; runs the submission.
    "prepare_global_task",
    "run_global_evaluation",
}


def test_tools_registered_with_annotations():
    tools = anyio.run(server.mcp.list_tools)
    assert {tool.name for tool in tools} == TOOL_NAMES
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.open_world_hint is False
        if tool.name in RUNNING:
            assert tool.annotations.read_only_hint is False
            assert tool.annotations.destructive_hint is False
        else:
            assert tool.annotations.read_only_hint is True


def test_instructions_are_short():
    assert len(server.INSTRUCTIONS.splitlines()) <= 12


def test_call_list_markers_through_server():
    async def call():
        return await server.mcp.call_tool("list_markers", {})

    result = anyio.run(call)
    assert "forbid_imports" in str(result)


def test_tool_error_for_relative_path():
    async def call():
        return await server.mcp.call_tool(
            "summarize_report", {"report_path": "report.json"}
        )

    with pytest.raises(ToolError, match="must be an absolute path"):
        anyio.run(call)


def test_package_import_does_not_import_mcp():
    code = (
        "import pythonarchtesting, pythonarchtesting.rules, sys; "
        "print('mcp' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False"
