"""Unit tests for the exclusion filter service.

Covers all 7 ConditionalOperator values, type coercion, OR semantics,
missing fields, None values, and empty rules edge case.
"""
import pytest
from app.schemas.exclusion_rule import ExclusionRule
from app.services.exclusion_filter import apply_exclusion_rules


def _rule(source_field: str, operator: str, value: str) -> ExclusionRule:
    """Helper to build an ExclusionRule quickly."""
    return ExclusionRule(source_field=source_field, operator=operator, value=value)


class TestApplyExclusionRulesEmptyRules:
    def test_empty_rules_returns_all_records(self):
        records = [{"name": "vm1"}, {"name": "vm2"}]
        passed, filtered_count = apply_exclusion_rules(records, [])
        assert passed == records
        assert filtered_count == 0


class TestEqualsOperator:
    def test_equals_excludes_matching_records_with_type_coercion(self):
        """Proxmox returns template=1 (int), rule value is '1' (str). Should match."""
        records = [
            {"name": "vm1", "template": 0},
            {"name": "vm2", "template": 1},
            {"name": "vm3", "template": 0},
        ]
        rules = [_rule("template", "equals", "1")]
        passed, filtered_count = apply_exclusion_rules(records, rules)
        assert len(passed) == 2
        assert filtered_count == 1
        assert all(r["template"] == 0 for r in passed)


class TestNotEqualsOperator:
    def test_not_equals_excludes_non_matching_records(self):
        records = [
            {"name": "vm1", "status": "running"},
            {"name": "vm2", "status": "stopped"},
            {"name": "vm3", "status": "running"},
        ]
        rules = [_rule("status", "not_equals", "running")]
        passed, filtered_count = apply_exclusion_rules(records, rules)
        assert len(passed) == 2
        assert filtered_count == 1
        assert all(r["status"] == "running" for r in passed)


class TestContainsOperator:
    def test_contains_excludes_records_containing_substring(self):
        records = [
            {"name": "prod-server-01"},
            {"name": "test-server-01"},
            {"name": "prod-server-02"},
        ]
        rules = [_rule("name", "contains", "test")]
        passed, filtered_count = apply_exclusion_rules(records, rules)
        assert len(passed) == 2
        assert filtered_count == 1
        assert all("test" not in r["name"] for r in passed)


class TestStartsWithOperator:
    def test_starts_with_excludes_records_starting_with_prefix(self):
        records = [
            {"hostname": "dev-app-01"},
            {"hostname": "prod-app-01"},
            {"hostname": "dev-db-01"},
        ]
        rules = [_rule("hostname", "starts_with", "dev-")]
        passed, filtered_count = apply_exclusion_rules(records, rules)
        assert len(passed) == 1
        assert filtered_count == 2
        assert passed[0]["hostname"] == "prod-app-01"


class TestEndsWithOperator:
    def test_ends_with_excludes_records_ending_with_suffix(self):
        records = [
            {"filename": "report.pdf"},
            {"filename": "data.csv"},
            {"filename": "notes.pdf"},
        ]
        rules = [_rule("filename", "ends_with", ".pdf")]
        passed, filtered_count = apply_exclusion_rules(records, rules)
        assert len(passed) == 1
        assert filtered_count == 2
        assert passed[0]["filename"] == "data.csv"


class TestRegexOperator:
    def test_regex_excludes_matching_records(self):
        records = [
            {"ip": "192.168.1.1"},
            {"ip": "10.0.0.1"},
            {"ip": "192.168.2.5"},
        ]
        rules = [_rule("ip", "regex", r"^192\.168\..*")]
        passed, filtered_count = apply_exclusion_rules(records, rules)
        assert len(passed) == 1
        assert filtered_count == 2
        assert passed[0]["ip"] == "10.0.0.1"


class TestInListOperator:
    def test_in_list_excludes_records_matching_any_list_item(self):
        records = [
            {"env": "prod"},
            {"env": "staging"},
            {"env": "dev"},
            {"env": "qa"},
        ]
        rules = [_rule("env", "in_list", "dev, staging, qa")]
        passed, filtered_count = apply_exclusion_rules(records, rules)
        assert len(passed) == 1
        assert filtered_count == 3
        assert passed[0]["env"] == "prod"


class TestOrSemantics:
    def test_multiple_rules_or_semantics(self):
        """If ANY rule matches, the record is excluded."""
        records = [
            {"name": "vm1", "template": 0, "status": "running"},
            {"name": "vm2", "template": 1, "status": "running"},
            {"name": "vm3", "template": 0, "status": "stopped"},
            {"name": "vm4", "template": 1, "status": "stopped"},
        ]
        rules = [
            _rule("template", "equals", "1"),
            _rule("status", "equals", "stopped"),
        ]
        passed, filtered_count = apply_exclusion_rules(records, rules)
        # vm1 passes (template=0, status=running)
        # vm2 excluded (template=1)
        # vm3 excluded (status=stopped)
        # vm4 excluded (template=1 AND status=stopped, but OR means either triggers)
        assert len(passed) == 1
        assert filtered_count == 3
        assert passed[0]["name"] == "vm1"


class TestMissingAndNoneFields:
    def test_missing_source_field_does_not_match(self):
        """Record without the source_field should NOT be excluded."""
        records = [
            {"name": "vm1"},  # no 'template' field at all
            {"name": "vm2", "template": 1},
        ]
        rules = [_rule("template", "equals", "1")]
        passed, filtered_count = apply_exclusion_rules(records, rules)
        assert len(passed) == 1
        assert filtered_count == 1
        assert passed[0]["name"] == "vm1"

    def test_none_value_for_source_field_does_not_match(self):
        """Record with None value for source_field should NOT be excluded."""
        records = [
            {"name": "vm1", "template": None},
            {"name": "vm2", "template": 1},
        ]
        rules = [_rule("template", "equals", "1")]
        passed, filtered_count = apply_exclusion_rules(records, rules)
        assert len(passed) == 1
        assert filtered_count == 1
        assert passed[0]["name"] == "vm1"
