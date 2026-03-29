"""Report output path helpers."""

from __future__ import annotations

from pathlib import Path


def resolve_bundle_root(output_path: str | Path) -> Path:
    """Resolve and return the root directory for a multi-file report bundle."""
    root = Path(output_path)
    return root


def markdown_bundle_index(root: Path) -> Path:
    return root / "report.md"


def markdown_target_page(root: Path, target_id: str) -> Path:
    return root / "targets" / f"{target_id}.md"
