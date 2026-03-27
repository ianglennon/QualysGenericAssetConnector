"""Tests for Qualys CSAM payload formatter - custom attribute transformation."""
import pytest
from app.services.qualys_formatter import format_asset_for_qualys


def test_custom_attributes_collected_into_dict():
    record = {
        "instanceUuid": "abc-123",
        "customAttribute.environment": "prod",
        "customAttribute.cost_center": "IT",
    }
    asset = format_asset_for_qualys(record)
    assert asset["coreAttributes"]["customConnectorAttributes"] == {
        "environment": "prod",
        "cost_center": "IT",
    }


def test_no_custom_attributes_omits_key():
    record = {"instanceUuid": "abc-123", "hostName": "server1"}
    asset = format_asset_for_qualys(record)
    assert "customConnectorAttributes" not in asset["coreAttributes"]


def test_custom_attributes_coexist_with_identity_and_core():
    record = {
        "instanceUuid": "abc-123",
        "sourceNativeKey": "src-1",
        "operatingSystem": "Linux",
        "customAttribute.team": "platform",
    }
    asset = format_asset_for_qualys(record)
    assert asset["identityAttributes"]["instanceUuid"] == "abc-123"
    assert asset["identityAttributes"]["sourceNativeKey"] == "src-1"
    assert asset["coreAttributes"]["operatingSystem"] == "Linux"
    assert asset["coreAttributes"]["customConnectorAttributes"] == {"team": "platform"}


def test_old_passthrough_replaced_by_prefix_collection():
    record = {
        "customConnectorAttributes": {"old": "value"},
        "customAttribute.new_key": "new_value",
    }
    asset = format_asset_for_qualys(record)
    # The customAttribute.* prefix collection should produce the dict
    assert asset["coreAttributes"]["customConnectorAttributes"] == {"new_key": "new_value"}


def test_custom_attribute_mixed_value_types():
    record = {
        "customAttribute.str_val": "hello",
        "customAttribute.num_val": 42,
        "customAttribute.bool_val": True,
    }
    asset = format_asset_for_qualys(record)
    ca = asset["coreAttributes"]["customConnectorAttributes"]
    assert ca["str_val"] == "hello"
    assert ca["num_val"] == 42
    assert ca["bool_val"] is True
