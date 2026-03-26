"""Nested path resolver for dot-notation with bracket indices.

Resolves paths like "address.city", "items[0].name", "data[2].tags[0]"
against nested dict/list structures. Returns None for any missing
intermediate key, non-dict intermediate, or out-of-range index.

Exports:
    resolve_path(record: dict, path: str) -> Any
"""

import re
from typing import Any

# Matches either a dict key segment or a bracketed integer index.
# Group 1: key name (letters, digits, hyphens, underscores)
# Group 2: integer index inside brackets
_SEGMENT_RE = re.compile(r'([^.\[\]]+)|\[(\d+)\]')


def resolve_path(record: dict, path: str) -> Any:
    """Traverse a nested dict/list structure using a dot-notation path.

    Args:
        record: The root dictionary to traverse.
        path: Dot-separated path with optional [N] bracket indices.
              Examples: "a.b", "items[0].name", "data[2].tags[0]"

    Returns:
        The value at the resolved path, or None if any intermediate
        is missing, not the expected type, or an index is out of range.
    """
    if not path:
        return None

    current: Any = record
    for match in _SEGMENT_RE.finditer(path):
        key, index = match.group(1), match.group(2)
        if key is not None:
            if not isinstance(current, dict):
                return None
            if key not in current:
                return None
            current = current[key]
        elif index is not None:
            idx = int(index)
            if not isinstance(current, list):
                return None
            if idx >= len(current) or idx < 0:
                return None
            current = current[idx]
    return current
