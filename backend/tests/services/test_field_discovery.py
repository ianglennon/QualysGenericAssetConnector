"""
Unit tests for the field_discovery service and canvas-aware discovery logic.

Tests cover:
- _python_type: JSON schema type detection
- flatten_fields: Recursive dict flattening with dot notation
- merge_fields_across_records: Field union across multiple records
- Canvas-aware discovery: _merge_parent_context + merge_fields_across_records
  for parent+child field merging with _parent.* prefix
"""
import pytest

from app.services.field_discovery import _python_type, flatten_fields, merge_fields_across_records
from app.services.fan_out_executor import _merge_parent_context
from app.services.template_resolver import resolve_path, TemplateResolutionError


# ---------------------------------------------------------------------------
# _python_type tests
# ---------------------------------------------------------------------------

def test_python_type():
    """_python_type maps Python primitives to JSON schema type strings.

    CRITICAL: True/False must return 'boolean', not 'number' — bool is a
    subclass of int in Python, so bool must be checked before int.
    """
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
    record = {"a": {"b": {"c": 1}}}
    fields = flatten_fields(record)
    paths = {f["path"]: f for f in fields}
    assert "a.b.c" in paths
    entry = paths["a.b.c"]
    assert entry["type"] == "number"
    assert entry["sample_value"] == 1


def test_flatten_array_objects():
    """Arrays of objects are expanded using bracket notation on the first element.

    {"items": [{"ip": "1.2.3.4"}]} → path "items[].ip", type "string"
    Phase 48: Changed from [0] to [] notation for array child fields.
    """
    record = {"items": [{"ip": "1.2.3.4"}]}
    fields = flatten_fields(record)
    paths = {f["path"]: f for f in fields}
    assert "items[].ip" in paths
    entry = paths["items[].ip"]
    assert entry["type"] == "string"
    assert entry.get("is_array_child") is True
    assert entry.get("parent_array_path") == "items"


def test_flatten_array_primitives():
    """Arrays of primitive values are surfaced as a single entry with type "array".

    {"tags": ["linux", "prod"]} → path "tags", type "array", sample_value is the list
    """
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


# ---------------------------------------------------------------------------
# Canvas-aware field discovery tests
# ---------------------------------------------------------------------------

def test_canvas_discovery_returns_parent_fields():
    """Canvas discovery returns both child-native and _parent.* fields (D-09).

    Simulates the merging that happens during canvas-aware discovery:
    parent records are merged into child records with _parent.* prefix,
    then merge_fields_across_records extracts the unified field list.
    """
    parent_records = [
        {"id": "1", "name": "server1"},
        {"id": "2", "name": "server2"},
    ]
    child_records = [
        {"cpu": "4", "ram": "16"},
        {"cpu": "8", "ram": "32"},
    ]

    # Simulate the merge that discover_canvas_endpoint_fields does
    merged = []
    for parent_rec in parent_records:
        ancestor_context = _merge_parent_context(parent_rec, {})
        for child_rec in child_records:
            merged.append(_merge_parent_context(child_rec, ancestor_context))

    fields = merge_fields_across_records(merged)
    paths = {f["path"] for f in fields}

    # Child-native fields
    assert "cpu" in paths
    assert "ram" in paths
    # _parent.* fields from parent
    assert "_parent.id" in paths
    assert "_parent.name" in paths


def test_canvas_discovery_samples_three_parents():
    """Canvas discovery samples only 3 parent records per D-11.

    Creates 5 parent records but only the first 3 should be used.
    The 4th and 5th parents have a unique field 'extra' that should NOT
    appear in the merged field list if only 3 are sampled.
    """
    DISCOVERY_SAMPLE_SIZE = 3  # Mirror the constant from canvas_endpoints.py

    parent_records = [
        {"id": str(i), "name": f"server{i}"}
        for i in range(5)
    ]
    # Add unique field only to parent records beyond the sample size
    parent_records[3]["extra"] = "should_not_appear"
    parent_records[4]["extra"] = "should_not_appear"

    child_records = [{"cpu": "4"}]

    # Only sample first 3 parents
    sampled_parents = parent_records[:DISCOVERY_SAMPLE_SIZE]
    merged = []
    for parent_rec in sampled_parents:
        ancestor_context = _merge_parent_context(parent_rec, {})
        for child_rec in child_records:
            merged.append(_merge_parent_context(child_rec, ancestor_context))

    fields = merge_fields_across_records(merged)
    paths = {f["path"] for f in fields}

    assert "cpu" in paths
    assert "_parent.id" in paths
    assert "_parent.name" in paths
    # The 'extra' field from parents 4 and 5 should NOT appear
    assert "_parent.extra" not in paths
    # Verify we only processed 3 parents
    assert len(merged) == 3  # 3 parents * 1 child record each


def test_canvas_discovery_skips_failed_template_resolution():
    """Canvas discovery skips parents that fail template resolution.

    Simulates 3 parent records where 1 fails resolve_path due to a missing
    field. The other 2 should produce valid merged fields.
    """
    parent_records = [
        {"id": "1", "name": "server1"},
        {"id": "2"},  # Missing 'name' field -- will cause TemplateResolutionError
        {"id": "3", "name": "server3"},
    ]
    child_records = [{"cpu": "4"}]
    path_template = "/nodes/{node_name}/vms"
    variable_extractions = {"node_name": "name"}

    merged = []
    for parent_rec in parent_records:
        try:
            resolve_path(path_template, parent_rec, variable_extractions)
        except TemplateResolutionError:
            continue  # Skip this parent, just like the endpoint does

        ancestor_context = _merge_parent_context(parent_rec, {})
        for child_rec in child_records:
            merged.append(_merge_parent_context(child_rec, ancestor_context))

    # 2 of 3 parents succeeded
    assert len(merged) == 2
    fields = merge_fields_across_records(merged)
    paths = {f["path"] for f in fields}

    assert "cpu" in paths
    assert "_parent.id" in paths
    assert "_parent.name" in paths


def test_merge_parent_context_produces_parent_prefix():
    """_merge_parent_context adds _parent.* prefix to ancestor fields.

    Direct test of the merging function used in canvas-aware discovery.
    """
    child = {"cpu": 4, "ram": 16}
    ancestor = {"id": "1", "name": "srv"}

    result = _merge_parent_context(child, ancestor)

    assert result["cpu"] == 4
    assert result["ram"] == 16
    assert result["_parent.id"] == "1"
    assert result["_parent.name"] == "srv"
    # Original child keys preserved
    assert "id" not in result
    assert "name" not in result


def test_canvas_discovery_all_samples_fail_returns_empty():
    """When all parent samples fail template resolution, empty fields returned.

    All 3 parent records are missing the required field for template resolution.
    The discovery logic should return an empty merged record list.
    """
    parent_records = [
        {"id": "1"},  # Missing 'name'
        {"id": "2"},  # Missing 'name'
        {"id": "3"},  # Missing 'name'
    ]
    child_records = [{"cpu": "4"}]
    path_template = "/nodes/{node_name}/vms"
    variable_extractions = {"node_name": "name"}

    merged = []
    for parent_rec in parent_records:
        try:
            resolve_path(path_template, parent_rec, variable_extractions)
        except TemplateResolutionError:
            continue

        ancestor_context = _merge_parent_context(parent_rec, {})
        for child_rec in child_records:
            merged.append(_merge_parent_context(child_rec, ancestor_context))

    # All failed -- empty
    assert len(merged) == 0
    fields = merge_fields_across_records(merged)
    assert fields == []
