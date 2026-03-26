"""Unit tests for the path resolver utility.

Tests resolve_path for dot-notation traversal, bracket indices,
missing keys, and edge cases. Also tests auto_detect_data_root.
"""

from app.services.path_resolver import resolve_path
from app.services.field_discovery import auto_detect_data_root


class TestResolvePath:
    def test_nested_dict(self):
        assert resolve_path({"a": {"b": 1}}, "a.b") == 1

    def test_array_index(self):
        assert resolve_path({"items": [{"x": 1}]}, "items[0].x") == 1

    def test_none_value(self):
        """resolve_path returns None for keys that exist but have None value."""
        assert resolve_path({"a": {"b": None}}, "a.b") is None

    def test_missing_intermediate(self):
        assert resolve_path({"a": 1}, "a.b.c") is None

    def test_index_out_of_range(self):
        assert resolve_path({"a": [1, 2, 3]}, "a[5]") is None

    def test_dots_traverse_not_flat(self):
        """Dots always mean traversal, not flat key lookup."""
        assert resolve_path({"flat.key": 42}, "flat.key") is None

    def test_top_level_key(self):
        assert resolve_path({"name": "test"}, "name") == "test"

    def test_deep_nesting(self):
        data = {"a": {"b": {"c": {"d": 99}}}}
        assert resolve_path(data, "a.b.c.d") == 99

    def test_array_of_objects(self):
        data = {"users": [{"name": "Alice"}, {"name": "Bob"}]}
        assert resolve_path(data, "users[1].name") == "Bob"

    def test_empty_path(self):
        assert resolve_path({"a": 1}, "") is None

    def test_empty_dict(self):
        assert resolve_path({}, "a.b") is None


class TestAutoDetectDataRoot:
    def test_single_key_array_of_dicts(self):
        assert auto_detect_data_root({"result": [{"id": 1}]}) == "result"

    def test_multiple_keys(self):
        assert auto_detect_data_root({"a": 1, "b": 2}) is None

    def test_value_not_array_of_dicts(self):
        assert auto_detect_data_root({"data": "string"}) is None

    def test_not_a_dict(self):
        assert auto_detect_data_root([{"id": 1}]) is None

    def test_empty_array(self):
        assert auto_detect_data_root({"data": []}) is None

    def test_array_of_primitives(self):
        assert auto_detect_data_root({"tags": ["a", "b"]}) is None
