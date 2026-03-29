"""
Dictionary key definitions for consistent data structures.
"""

from typing import Final


class DictKeys:
    """Centralized dictionary key definitions."""

    class Cache:
        FILE_PATH: Final[str] = "file_path"
        MTIME: Final[str] = "mtime"
        CONTENT_HASH: Final[str] = "content_hash"
        METADATA: Final[str] = "metadata"
        SIZE: Final[str] = "size"
        MAX_SIZE: Final[str] = "max_size"
        HITS: Final[str] = "hits"
        MISSES: Final[str] = "misses"
        HIT_RATE: Final[str] = "hit_rate"
