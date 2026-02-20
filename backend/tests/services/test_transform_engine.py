from app.schemas.field_mapping import (
    FieldMappingDirectCopy,
    FieldMappingStaticDefault,
    FieldMappingConditional,
    ConditionalMappingConfig,
    ConditionRule,
    ConditionalOperator,
)
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


# Conditional mapping tests


def test_conditional_first_match_wins():
    """Test that only the first matching condition is applied."""
    source = {"ip": "10.0.0.1"}
    mappings = [
        FieldMappingConditional(
            target_field="classification",
            conditional_config=ConditionalMappingConfig(
                conditions=[
                    ConditionRule(
                        operator=ConditionalOperator.contains,
                        source_field="ip",
                        target_value="10.",
                        value="PRIVATE",
                    ),
                    ConditionRule(
                        operator=ConditionalOperator.equals,
                        source_field="ip",
                        target_value="10.0.0.1",
                        value="SPECIFIC",
                    ),
                    ConditionRule(
                        operator=ConditionalOperator.contains,
                        source_field="ip",
                        target_value="0",
                        value="HAS_ZERO",
                    ),
                ]
            ),
        ),
    ]

    # First condition (contains "10.") should match and win
    assert apply_mappings(source, mappings) == {"classification": "PRIVATE"}


def test_conditional_fallback():
    """Test that fallback value is used when no conditions match."""
    source = {"ip": "8.8.8.8"}
    mappings = [
        FieldMappingConditional(
            target_field="classification",
            conditional_config=ConditionalMappingConfig(
                conditions=[
                    ConditionRule(
                        operator=ConditionalOperator.contains,
                        source_field="ip",
                        target_value="10.",
                        value="PRIVATE",
                    ),
                    ConditionRule(
                        operator=ConditionalOperator.contains,
                        source_field="ip",
                        target_value="192.168.",
                        value="PRIVATE",
                    ),
                ],
                fallback="PUBLIC",
            ),
        ),
    ]

    assert apply_mappings(source, mappings) == {"classification": "PUBLIC"}


def test_conditional_no_fallback_omits_field():
    """Test that field is omitted when no conditions match and no fallback defined."""
    source = {"ip": "8.8.8.8"}
    mappings = [
        FieldMappingConditional(
            target_field="classification",
            conditional_config=ConditionalMappingConfig(
                conditions=[
                    ConditionRule(
                        operator=ConditionalOperator.contains,
                        source_field="ip",
                        target_value="10.",
                        value="PRIVATE",
                    ),
                ],
                fallback=None,
            ),
        ),
    ]

    # Field should be omitted entirely
    assert apply_mappings(source, mappings) == {}


def test_conditional_operator_equals():
    """Test equals operator."""
    source = {"os": "Linux"}
    mappings = [
        FieldMappingConditional(
            target_field="os_family",
            conditional_config=ConditionalMappingConfig(
                conditions=[
                    ConditionRule(
                        operator=ConditionalOperator.equals,
                        source_field="os",
                        target_value="Linux",
                        value="Unix",
                    ),
                ]
            ),
        ),
    ]

    assert apply_mappings(source, mappings) == {"os_family": "Unix"}


def test_conditional_operator_not_equals():
    """Test not_equals operator."""
    source = {"os": "Windows"}
    mappings = [
        FieldMappingConditional(
            target_field="is_unix",
            conditional_config=ConditionalMappingConfig(
                conditions=[
                    ConditionRule(
                        operator=ConditionalOperator.not_equals,
                        source_field="os",
                        target_value="Windows",
                        value="yes",
                    ),
                ],
                fallback="no",
            ),
        ),
    ]

    # not_equals check fails (os IS Windows), so fallback is used
    assert apply_mappings(source, mappings) == {"is_unix": "no"}


def test_conditional_operator_contains():
    """Test contains operator."""
    source = {"hostname": "prod-web-01"}
    mappings = [
        FieldMappingConditional(
            target_field="environment",
            conditional_config=ConditionalMappingConfig(
                conditions=[
                    ConditionRule(
                        operator=ConditionalOperator.contains,
                        source_field="hostname",
                        target_value="prod",
                        value="production",
                    ),
                ]
            ),
        ),
    ]

    assert apply_mappings(source, mappings) == {"environment": "production"}


def test_conditional_operator_regex():
    """Test regex operator."""
    source = {"ip": "10.0.0.1"}
    mappings = [
        FieldMappingConditional(
            target_field="classification",
            conditional_config=ConditionalMappingConfig(
                conditions=[
                    ConditionRule(
                        operator=ConditionalOperator.regex,
                        source_field="ip",
                        target_value=r"^10\.",
                        value="RFC1918",
                    ),
                ]
            ),
        ),
    ]

    assert apply_mappings(source, mappings) == {"classification": "RFC1918"}


def test_conditional_operator_in_list():
    """Test in_list operator."""
    source = {"environment": "prod"}
    mappings = [
        FieldMappingConditional(
            target_field="is_production",
            conditional_config=ConditionalMappingConfig(
                conditions=[
                    ConditionRule(
                        operator=ConditionalOperator.in_list,
                        source_field="environment",
                        target_value=["prod", "production", "live"],
                        value="yes",
                    ),
                ],
                fallback="no",
            ),
        ),
    ]

    assert apply_mappings(source, mappings) == {"is_production": "yes"}


def test_conditional_missing_source_field():
    """Test that missing source field causes condition to fail."""
    source = {"hostname": "asset-1"}  # No "ip" field
    mappings = [
        FieldMappingConditional(
            target_field="classification",
            conditional_config=ConditionalMappingConfig(
                conditions=[
                    ConditionRule(
                        operator=ConditionalOperator.contains,
                        source_field="ip",
                        target_value="10.",
                        value="PRIVATE",
                    ),
                ],
                fallback="UNKNOWN",
            ),
        ),
    ]

    # Missing source field → condition fails → fallback used
    assert apply_mappings(source, mappings) == {"classification": "UNKNOWN"}


def test_null_values_filtered():
    """Test that null/None values are excluded from output."""
    source = {"hostname": "asset-1", "ip": None, "empty_field": ""}
    mappings = [
        FieldMappingDirectCopy(target_field="name", source_field="hostname"),
        FieldMappingDirectCopy(target_field="address", source_field="ip"),
        FieldMappingDirectCopy(target_field="notes", source_field="empty_field"),
        FieldMappingConditional(
            target_field="classification",
            conditional_config=ConditionalMappingConfig(
                conditions=[
                    ConditionRule(
                        operator=ConditionalOperator.equals,
                        source_field="ip",
                        target_value="10.0.0.1",
                        value="PRIVATE",
                    ),
                ],
                fallback=None,
            ),
        ),
    ]

    # ip is None → excluded from output
    # classification has no match and fallback=None → excluded
    # empty_field="" is NOT None → included
    result = apply_mappings(source, mappings)
    assert result == {"name": "asset-1", "notes": ""}
    assert "address" not in result
    assert "classification" not in result
