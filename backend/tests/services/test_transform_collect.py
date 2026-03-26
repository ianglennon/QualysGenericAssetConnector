"""Unit tests for collect mapping type and nested path resolution in transform engine."""

import json

from pydantic import TypeAdapter

from app.schemas.field_mapping import FieldMappingRule


def _make_rule(data: dict) -> FieldMappingRule:
    """Helper to build a FieldMappingRule from a dict."""
    adapter = TypeAdapter(FieldMappingRule)
    return adapter.validate_python(data)


def _apply(record: dict, rules: list) -> dict:
    from app.services.transform_engine import apply_mappings
    return apply_mappings(record, rules)


class TestCollectMapping:
    def test_collect_basic(self):
        """Collect extracts field from array elements as JSON list."""
        record = {"interfaces": [{"ip": "10.0.0.1"}, {"ip": "10.0.0.2"}]}
        rule = _make_rule({
            "mapping_type": "collect",
            "target_field": "ips",
            "array_path": "interfaces",
            "extract_field": "ip",
        })
        result = _apply(record, [rule])
        assert result["ips"] == json.dumps(["10.0.0.1", "10.0.0.2"])

    def test_collect_with_separator(self):
        """Collect with separator joins values instead of JSON list."""
        record = {"interfaces": [{"ip": "10.0.0.1"}, {"ip": "10.0.0.2"}]}
        rule = _make_rule({
            "mapping_type": "collect",
            "target_field": "ips",
            "array_path": "interfaces",
            "extract_field": "ip",
            "separator": ",",
        })
        result = _apply(record, [rule])
        assert result["ips"] == "10.0.0.1,10.0.0.2"

    def test_collect_with_filter(self):
        """Collect filters array elements before extraction."""
        record = {
            "interfaces": [
                {"ip": "10.0.0.1", "type": "inet"},
                {"ip": "192.168.1.1", "type": "inet6"},
                {"ip": "172.16.0.1", "type": "inet"},
            ]
        }
        rule = _make_rule({
            "mapping_type": "collect",
            "target_field": "ipv4",
            "array_path": "interfaces",
            "extract_field": "ip",
            "collect_filter": {
                "field": "type",
                "operator": "equals",
                "value": "inet",
            },
        })
        result = _apply(record, [rule])
        assert json.loads(result["ipv4"]) == ["10.0.0.1", "172.16.0.1"]

    def test_collect_no_extract_field(self):
        """Collect without extract_field serializes whole array elements."""
        record = {"tags": [{"key": "env", "value": "prod"}, {"key": "team", "value": "ops"}]}
        rule = _make_rule({
            "mapping_type": "collect",
            "target_field": "all_tags",
            "array_path": "tags",
        })
        result = _apply(record, [rule])
        parsed = json.loads(result["all_tags"])
        assert len(parsed) == 2
        assert parsed[0] == {"key": "env", "value": "prod"}

    def test_collect_missing_array(self):
        """Collect on non-existent array path produces no output."""
        record = {"name": "test"}
        rule = _make_rule({
            "mapping_type": "collect",
            "target_field": "ips",
            "array_path": "interfaces",
            "extract_field": "ip",
        })
        result = _apply(record, [rule])
        assert "ips" not in result

    def test_collect_nested_array_path(self):
        """Collect works with nested array path using dot notation."""
        record = {"network": {"interfaces": [{"ip": "10.0.0.1"}]}}
        rule = _make_rule({
            "mapping_type": "collect",
            "target_field": "ips",
            "array_path": "network.interfaces",
            "extract_field": "ip",
        })
        result = _apply(record, [rule])
        assert json.loads(result["ips"]) == ["10.0.0.1"]


class TestDirectCopyNested:
    def test_direct_copy_nested(self):
        """Direct copy with dot-notation resolves nested path."""
        record = {"address": {"city": "London"}}
        rule = _make_rule({
            "mapping_type": "direct_copy",
            "target_field": "city",
            "source_field": "address.city",
        })
        result = _apply(record, [rule])
        assert result["city"] == "London"

    def test_direct_copy_flat_priority(self):
        """When record has top-level key with dots, flat lookup takes priority."""
        record = {"address.city": "FlatValue", "address": {"city": "NestedValue"}}
        rule = _make_rule({
            "mapping_type": "direct_copy",
            "target_field": "city",
            "source_field": "address.city",
        })
        result = _apply(record, [rule])
        assert result["city"] == "FlatValue"
