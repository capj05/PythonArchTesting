"""The submission's source as the core extracts it, read once per tool call.

``scan`` runs the core's extraction (``prepare_source``) over a submission
and keeps the config it applied. Every step of one tool call that needs the
submission's entities (discovery, the self-task, the check that the core can
bind the task, the class families) takes them from that one ``Scan`` instead
of reading the source again; ``entities_of`` reads it again only when the
step would apply another config file (a ``.pythonarchtesting`` beside the task
directory), so what each step sees is exactly what it would have read itself.
``Scan``, ``extract`` and ``entities_of`` live in the core
(``runner.source_prep``), which ``prepare_task`` uses too; they are
re-exported here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pythonarchtesting.entities import Entity
from pythonarchtesting.runner.source_prep import (
    SYNTAX_CHECK,
    Scan,
    entities_of,
    extract,
)


def scan(
    path: Path, config: Optional[str] = None, *, config_from: Optional[Path] = None
) -> Scan:
    """The extraction of ``path`` under the config ``resolve_config`` finds
    for ``config_from`` (default ``path``), or the file ``config``."""
    from pythonarchtesting.mcp_server.evaluation import resolve_config

    loaded, applied = resolve_config(Path(config_from or path), config)
    return extract(path, loaded, applied)


def source_entities(submission: Path, config: Optional[str] = None) -> list[Entity]:
    """The submission's entities as the core extracts them: the same ones
    ``bind_task`` resolves the roles against (``mcp_server.tasks._bind``)."""
    return list(scan(Path(submission), config).entities)


__all__ = ["SYNTAX_CHECK", "Scan", "entities_of", "extract", "scan", "source_entities"]
