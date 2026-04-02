"""Tests for record_assembler.assemble_qualys_record().

Covers: single endpoint, multi-endpoint merge, multi-record downstream
first-match, missing/empty endpoints, and endpoint order.
"""

from app.services.fan_out_executor import TraversalRecord
from app.services.record_assembler import assemble_qualys_record


class TestSingleEndpoint:
    """Test 1: Base-only -- endpoint_outputs has one key with one dict."""

    def test_single_base_endpoint(self):
        tr = TraversalRecord(
            raw_record={"id": "vm-1"},
            ancestor_context={},
            endpoint_outputs={
                "base-ce-1": [{"hostName": "vm-1", "instanceUuid": "uuid-1"}],
            },
        )
        result = assemble_qualys_record(tr, ["base-ce-1"])
        assert result == {"hostName": "vm-1", "instanceUuid": "uuid-1"}


class TestUpstreamPlusBase:
    """Test 2: Upstream + base -- fields from both present."""

    def test_upstream_and_base_merged(self):
        tr = TraversalRecord(
            raw_record={"id": "vm-1"},
            ancestor_context={},
            endpoint_outputs={
                "upstream-ce-1": [{"nodeName": "node-1"}],
                "base-ce-1": [{"hostName": "vm-1", "instanceUuid": "uuid-1"}],
            },
        )
        result = assemble_qualys_record(tr, ["upstream-ce-1", "base-ce-1"])
        assert result == {
            "nodeName": "node-1",
            "hostName": "vm-1",
            "instanceUuid": "uuid-1",
        }


class TestFullChain:
    """Test 3: Upstream + base + downstream (single record each)."""

    def test_three_endpoint_merge(self):
        tr = TraversalRecord(
            raw_record={"id": "vm-1"},
            ancestor_context={},
            endpoint_outputs={
                "upstream-ce-1": [{"nodeName": "node-1"}],
                "base-ce-1": [{"hostName": "vm-1", "instanceUuid": "uuid-1"}],
                "downstream-ce-1": [{"agentVersion": "5.0"}],
            },
        )
        result = assemble_qualys_record(
            tr, ["upstream-ce-1", "base-ce-1", "downstream-ce-1"]
        )
        assert result == {
            "nodeName": "node-1",
            "hostName": "vm-1",
            "instanceUuid": "uuid-1",
            "agentVersion": "5.0",
        }


class TestDownstreamMultiRecord:
    """Test 4: Downstream with multiple records -- first-match (D-05)."""

    def test_first_record_wins(self):
        tr = TraversalRecord(
            raw_record={"id": "vm-1"},
            ancestor_context={},
            endpoint_outputs={
                "base-ce-1": [{"hostName": "vm-1"}],
                "downstream-ce-1": [
                    {"agentVersion": "5.0", "os": "Linux"},
                    {"agentVersion": "4.0", "os": "Windows"},
                ],
            },
        )
        result = assemble_qualys_record(tr, ["base-ce-1", "downstream-ce-1"])
        assert result == {
            "hostName": "vm-1",
            "agentVersion": "5.0",
            "os": "Linux",
        }


class TestEnrichmentGap:
    """Test 5: Missing endpoint in endpoint_outputs -- no KeyError."""

    def test_missing_endpoint_skipped(self):
        tr = TraversalRecord(
            raw_record={"id": "vm-1"},
            ancestor_context={},
            endpoint_outputs={
                "base-ce-1": [{"hostName": "vm-1"}],
                # "downstream-ce-1" is missing entirely
            },
        )
        result = assemble_qualys_record(
            tr, ["base-ce-1", "downstream-ce-1"]
        )
        assert result == {"hostName": "vm-1"}


class TestEmptyOutputsList:
    """Test 6: Empty endpoint_outputs list for an endpoint -- skipped."""

    def test_empty_list_skipped(self):
        tr = TraversalRecord(
            raw_record={"id": "vm-1"},
            ancestor_context={},
            endpoint_outputs={
                "base-ce-1": [{"hostName": "vm-1"}],
                "downstream-ce-1": [],
            },
        )
        result = assemble_qualys_record(
            tr, ["base-ce-1", "downstream-ce-1"]
        )
        assert result == {"hostName": "vm-1"}


class TestEndpointOrder:
    """Test 7: Endpoint order respected -- later endpoints overwrite earlier for same keys."""

    def test_order_determines_override(self):
        tr = TraversalRecord(
            raw_record={"id": "vm-1"},
            ancestor_context={},
            endpoint_outputs={
                "upstream-ce-1": [{"shared_field": "upstream_val", "only_upstream": "u"}],
                "base-ce-1": [{"shared_field": "base_val", "only_base": "b"}],
                "downstream-ce-1": [{"shared_field": "downstream_val", "only_downstream": "d"}],
            },
        )
        result = assemble_qualys_record(
            tr, ["upstream-ce-1", "base-ce-1", "downstream-ce-1"]
        )
        # Later endpoint wins for shared_field
        assert result["shared_field"] == "downstream_val"
        assert result["only_upstream"] == "u"
        assert result["only_base"] == "b"
        assert result["only_downstream"] == "d"
