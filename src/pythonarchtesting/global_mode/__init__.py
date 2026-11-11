"""Global mode: the taught principles checked in a student's project without a
reference solution. Each submission becomes its own reference (``selftask``),
so the existing core checks it unchanged. Importing the package does not load
the MCP layer (``pythonarchtesting.mcp_server``); the functions that run the
core import it when called."""

from pythonarchtesting.global_mode.discovery import (
    ESSENTIAL_ROLES,
    Override,
    discover_roles,
    split_by_base,
)
from pythonarchtesting.global_mode.model import (
    BoundEntity,
    PrincipleOutcome,
    RoleDiscovery,
)
from pythonarchtesting.global_mode.outcome import decide_status, judge_principle
from pythonarchtesting.global_mode.selftask import SelfTask, write_self_task
from pythonarchtesting.global_mode.summary import summarize_outcomes

__all__ = [
    "ESSENTIAL_ROLES",
    "BoundEntity",
    "Override",
    "PrincipleOutcome",
    "RoleDiscovery",
    "SelfTask",
    "decide_status",
    "discover_roles",
    "judge_principle",
    "split_by_base",
    "summarize_outcomes",
    "write_self_task",
]
