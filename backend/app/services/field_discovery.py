"""
Field discovery service for the Qualys Generic Asset Connector.

Provides utilities to introspect source API responses and extract a flat,
typed field list that operators can use for mapping configuration.

Exports:
    _python_type(value) -> str
    flatten_fields(obj, prefix, depth, results) -> list[dict]
    merge_fields_across_records(records) -> list[dict]
    auto_detect_data_root(payload) -> str | None
"""

from typing import Any

MAX_DEPTH = 5


def _python_type(value) -> str:
    """Return a JSON-schema-style type string for a Python value.

    IMPORTANT: bool must be checked before int because bool is a subclass of int
    in Python — isinstance(True, int) is True.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def flatten_fields(
    obj: dict,
    prefix: str = "",
    depth: int = 0,
    results: list | None = None,
) -> list:
    """Recursively walk a dict and emit a flat list of typed field descriptors.

    Args:
        obj: The dict to flatten.
        prefix: Dot-notation path prefix for the current recursion level.
        depth: Current recursion depth (0-indexed). Stops at MAX_DEPTH.
        results: Accumulator list; created on first call.

    Returns:
        List of dicts, each with keys: path (str), type (str), sample_value (any).
    """
    if results is None:
        results = []

    if depth >= MAX_DEPTH:
        return results

    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            flatten_fields(value, path, depth + 1, results)
        elif isinstance(value, list):
            # Determine if it's a list of objects or a list of primitives
            if value and isinstance(value[0], dict):
                # Array of objects — emit parent array entry, then recurse with [] notation
                results.append({
                    "path": path,
                    "type": "array",
                    "sample_value": f"[{len(value)} items]",
                    "is_array_parent": True,
                })
                child_prefix = f"{path}[]"
                before_count = len(results)
                flatten_fields(value[0], child_prefix, depth + 1, results)
                # Tag child fields with array metadata
                for i in range(before_count, len(results)):
                    results[i]["is_array_child"] = True
                    results[i]["parent_array_path"] = path
            else:
                # Array of primitives (or empty) — surface as a single "array" entry
                results.append({
                    "path": path,
                    "type": "array",
                    "sample_value": value[:3],
                })
        else:
            results.append({
                "path": path,
                "type": _python_type(value),
                "sample_value": value,
            })

    return results


def merge_fields_across_records(records: list) -> list:
    """Merge field discovery results from multiple source records.

    Iterates each record, flattens it, and unions the resulting paths.
    When the same path appears in multiple records, the first occurrence's
    sample_value is preserved (first-record-wins).

    Args:
        records: List of dicts (source API records from the first page).

    Returns:
        List of field dicts with unique paths; order follows first appearance.
    """
    seen: dict = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        for field in flatten_fields(record):
            path = field["path"]
            if path not in seen:
                seen[path] = field
    return list(seen.values())


def auto_detect_data_root(payload: Any) -> str | None:
    """Auto-detect a data root key in an API response.

    If the payload is a dict with exactly one key whose value is a non-empty
    list where the first element is a dict, return that key. This covers
    common wrapper patterns like {"result": [...]}, {"data": [...]}, etc.

    Args:
        payload: The raw API response payload.

    Returns:
        The wrapper key name, or None if no single-key array wrapper detected.
    """
    if not isinstance(payload, dict):
        return None
    if len(payload) != 1:
        return None
    key = next(iter(payload))
    value = payload[key]
    if not isinstance(value, list) or not value:
        return None
    if not isinstance(value[0], dict):
        return None
    return key
