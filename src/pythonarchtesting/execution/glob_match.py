from __future__ import annotations

import re
from functools import lru_cache
from typing import Sequence


def path_matches_any_glob(
    filepath: str,
    patterns: Sequence[str] | None,
) -> bool:
    if not patterns:
        return False
    return any(_compile(pattern).match(filepath) is not None for pattern in patterns)


@lru_cache(maxsize=512)
def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(_translate_pattern(pattern))


def _translate_pattern(pattern: str) -> str:
    parts = pattern.split("/")
    out: list[str] = []
    n = len(parts)
    i = 0
    while i < n:
        seg = parts[i]
        if seg == "**":
            if n == 1:
                out.append(".*")
            elif i == 0:
                out.append("(?:[^/]+/)*")
            elif i == n - 1:
                if out and out[-1] == "/":
                    out.pop()
                out.append("(?:/.*)?")
            else:
                out.append("(?:[^/]+/)*")
            i += 1
        else:
            out.append(_translate_segment(seg))
            if i < n - 1:
                out.append("/")
            i += 1
    return r"\A" + "".join(out) + r"\Z"


def _translate_segment(segment: str) -> str:
    out: list[str] = []
    for ch in segment:
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
    return "".join(out)


__all__ = ["path_matches_any_glob"]
