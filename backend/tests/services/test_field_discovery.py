"""
Unit tests for the field_discovery service (RED state — service does not exist yet).

These tests will fail when app.services.field_discovery does not exist:
- collection succeeds (all test functions are visible in --collect-only)
- execution raises pytest.skip or ImportError at run time (RED state)

Once the service is implemented in Wave 1, remove the try/except import block
and replace with a direct import — at that point all tests should pass.
"""
import pytest

try:
    from app.services.field_discovery import _python_type, flatten_fields, merge_fields_across_records
    _MODULE_MISSING = False
except ImportError:
    _MODULE_MISSING = True
    _python_type = None
    flatten_fields = None
    merge_fields_across_records = None


def _require_module():
    """Skip test if field_discovery module is not yet implemented."""
    if _MODULE_MISSING:
        pytest.skip("app.services.field_discovery not yet implemented (RED state)")


# ---------------------------------------------------------------------------
# _python_type tests
# ---------------------------------------------------------------------------

def test_python_type():
    """_python_type maps Python primitives to JSON schema type strings.

    CRITICAL: True/False must return 'boolean', not 'number' — bool is a
    subclass of int in Python, so bool must be checked before int.
    """
    _require_module()
    assert _python_type(True) == "boolean"
    assert _python_type(False) == "boolean"
    assert _python_type(42) == "number"
    assert _python_type(3.14) == "number"
    assert _python_type("hello") == "string"
    assert _python_type(None) == "null"
    assert _python_type([]) == "array"
    assert _python_type({}) == "object"


# ---------------------------------------------------------------------------
# flatten_fields tests
# ---------------------------------------------------------------------------

def test_flatten_nested():
    """Deeply nested objects are flattened with dot notation.

    {"a": {"b": {"c": 1}}} → one entry with path "a.b.c", type "number", sample_value 1
    """
    _require_module()
    record = {"a": {"b": {"c": 1}}}
    fields = flatten_fields(record)
    paths = {f["path"]: f for f in fields}
    assert "a.b.c" in paths
    entry = paths["a.b.c"]
    assert entry["type"] == "number"
    assert entry["sample_value"] == 1


def test_flatten_array_objects():
    """Arrays of objects are expanded using bracket-index notation on the first element.

    {"items": [{"ip": "1.2.3.4"}]} → path "items[0].ip", type "string"
    """
    _require_module()
    record = {"items": [{"ip": "1.2.3.4"}]}
    fields = flatten_fields(record)
    paths = {f["path"]: f for f in fields}
    assert "items[0].ip" in paths
    entry = paths["items[0].ip"]
    assert entry["type"] == "string"


def test_flatten_array_primitives():
    """Arrays of primitive values are surfaced as a single entry with type "array".

    {"tags": ["linux", "prod"]} → path "tags", type "array", sample_value is the list
    """
    _require_module()
    record = {"tags": ["linux", "prod"]}
    fields = flatten_fields(record)
    paths = {f["path"]: f for f in fields}
    assert "tags" in paths
    entry = paths["tags"]
    assert entry["type"] == "array"
    # sample_value should contain the original list value
    assert entry["sample_value"] == ["linux", "prod"]


def test_depth_cap():
    """Recursion stops at depth 5; no paths with 6 levels of nesting are emitted.

    Construct a dict nested 6 levels deep: {"a": {"b": {"c": {"d": {"e": {"f": 1}}}}}}
    Paths should stop at depth 5 — "a.b.c.d.e" is acceptable but not "a.b.c.d.e.f".
    """
    _require_module()
    record = {"a": {"b": {"c": {"d": {"e": {"f": 1}}}}}}
    fields = flatten_fields(record)
    paths = [f["path"] for f in fields]
    # No path should have more than 5 dot-separated segments (depth 6 = 6 segments)
    for path in paths:
        segments = path.split(".")
        assert len(segments) <= 5, f"Path exceeded depth cap: {path}"


# ---------------------------------------------------------------------------
# merge_fields_across_records tests
# ---------------------------------------------------------------------------

def test_merge_fields():
    """Fields from multiple records are merged into a single field list.

    Record 1 has field "a", record 2 has field "b" → merged result has both.
    When both records have the same field, record 1's value wins for sample_value.
    """
    _require_module()
    record1 = {"a": "value_a", "shared": "from_record1"}
    record2 = {"b": "value_b", "shared": "from_record2"}
    fields = merge_fields_across_records([record1, record2])
    paths = {f["path"]: f for f in fields}

    # Both fields must be present in the merged result
    assert "a" in paths
    assert "b" in paths
    assert "shared" in paths

    # Record 1's value wins for the shared field
    assert paths["shared"]["sample_value"] == "from_record1"
