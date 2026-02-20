from app.schemas.field_mapping import FieldMappingDirectCopy, FieldMappingStaticDefault
from app.services.transform_engine import apply_mappings


def test_apply_mappings_direct_copy():
    source = {"hostname": "asset-1"}
    mappings = [
        FieldMappingDirectCopy(target_field="name", source_field="hostname"),
    ]

    assert apply_mappings(source, mappings) == {"name": "asset-1"}


def test_apply_mappings_static_default():
    source = {"hostname": "asset-1"}
    mappings = [
        FieldMappingStaticDefault(target_field="environment", static_value="prod"),
    ]

    assert apply_mappings(source, mappings) == {"environment": "prod"}


def test_apply_mappings_mixed_rules():
    source = {"hostname": "asset-1", "ip": "10.0.0.5"}
    mappings = [
        FieldMappingDirectCopy(target_field="name", source_field="hostname"),
        FieldMappingStaticDefault(target_field="environment", static_value="prod"),
        FieldMappingDirectCopy(target_field="address", source_field="ip"),
    ]

    assert apply_mappings(source, mappings) == {
        "name": "asset-1",
        "environment": "prod",
        "address": "10.0.0.5",
    }


def test_apply_mappings_missing_source_field_omits_target():
    source = {"hostname": "asset-1"}
    mappings = [
        FieldMappingDirectCopy(target_field="name", source_field="hostname"),
        FieldMappingDirectCopy(target_field="address", source_field="ip"),
    ]

    assert apply_mappings(source, mappings) == {"name": "asset-1"}
