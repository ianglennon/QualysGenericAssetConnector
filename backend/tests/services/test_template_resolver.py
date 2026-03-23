import pytest
from app.services.template_resolver import (
    extract_variables,
    resolve_path,
    TemplateResolutionError,
)


# --- extract_variables tests ---


def test_extract_variables():
    assert extract_variables("/nodes/{name}/qemu/{vmid}") == ["name", "vmid"]


def test_extract_variables_empty():
    assert extract_variables("/api/v1/nodes") == []


def test_extract_variables_deduplicates():
    assert extract_variables("/api/{id}/sub/{id}") == ["id"]


# --- resolve_path: happy path ---


def test_resolve_single_variable():
    result = resolve_path(
        "/nodes/{name}/qemu",
        {"name": "pve1"},
        {"name": "name"},
    )
    assert result == "/nodes/pve1/qemu"


def test_resolve_multi_variable():
    result = resolve_path(
        "/nodes/{name}/qemu/{vmid}/agent",
        {"name": "pve1", "vmid": "100"},
        {"name": "name", "vmid": "vmid"},
    )
    assert result == "/nodes/pve1/qemu/100/agent"


def test_no_variables_passthrough():
    result = resolve_path("/api/v1/nodes", {}, {})
    assert result == "/api/v1/nodes"


# --- resolve_path: URL encoding / security ---


def test_url_encoding():
    result = resolve_path(
        "/hosts/{id}",
        {"id": "../../admin"},
        {"id": "id"},
    )
    assert result == "/hosts/..%2F..%2Fadmin"


def test_query_injection_prevention():
    result = resolve_path(
        "/hosts/{id}",
        {"id": "x?admin=true&drop=1"},
        {"id": "id"},
    )
    assert result == "/hosts/x%3Fadmin%3Dtrue%26drop%3D1"


def test_path_traversal_prevention():
    result = resolve_path(
        "/hosts/{id}/details",
        {"id": "node/../../etc"},
        {"id": "id"},
    )
    assert result == "/hosts/node%2F..%2F..%2Fetc/details"


# --- resolve_path: error cases ---


def test_missing_variable_error():
    with pytest.raises(TemplateResolutionError) as exc_info:
        resolve_path(
            "/hosts/{host_id}/details",
            {"name": "web-01"},
            {"host_id": "host_id"},
        )
    assert exc_info.value.variable == "host_id"


def test_null_value_error():
    with pytest.raises(TemplateResolutionError) as exc_info:
        resolve_path(
            "/hosts/{host_id}",
            {"host_id": None},
            {"host_id": "host_id"},
        )
    assert "null" in exc_info.value.reason


def test_no_extraction_rule_error():
    with pytest.raises(TemplateResolutionError) as exc_info:
        resolve_path("/hosts/{host_id}", {}, {})
    assert "no extraction rule" in exc_info.value.reason


# --- resolve_path: dot-notation ---


def test_dot_notation_nested():
    result = resolve_path(
        "/resources/{rid}",
        {"data": {"id": "res-42"}},
        {"rid": "data.id"},
    )
    assert result == "/resources/res-42"


def test_dot_notation_deep():
    result = resolve_path(
        "/items/{x}",
        {"a": {"b": {"c": "deep"}}},
        {"x": "a.b.c"},
    )
    assert result == "/items/deep"


def test_dot_notation_missing_segment():
    with pytest.raises(TemplateResolutionError):
        resolve_path(
            "/items/{x}",
            {"a": {"z": 1}},
            {"x": "a.b.c"},
        )


# --- resolve_path: type coercion ---


def test_numeric_value_converted_to_string():
    result = resolve_path(
        "/vms/{vmid}",
        {"vmid": 100},
        {"vmid": "vmid"},
    )
    assert result == "/vms/100"
