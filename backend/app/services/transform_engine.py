import re
from typing import Iterable

from app.schemas.field_mapping import FieldMappingRule, ConditionRule


def _match_condition(record: dict, condition: ConditionRule) -> bool:
    """Evaluate a single condition against source record.
    
    Operators: equals, not_equals, contains, regex, in_list
    Returns False if source_field missing or value is None.
    """
    source_field = condition.source_field
    value = record.get(source_field)
    target = condition.target_value
    
    if value is None:
        return False
    
    operator = condition.operator.value
    if operator == "equals":
        return value == target
    elif operator == "not_equals":
        return value != target
    elif operator == "contains":
        return target in str(value)
    elif operator == "regex":
        return re.match(str(target), str(value)) is not None
    elif operator == "in_list":
        # target should be a list for in_list operator
        return value in target
    else:
        return False


def apply_mappings(source_record: dict, mappings: Iterable[FieldMappingRule]) -> dict:
    transformed: dict = {}
    for mapping in mappings:
        if mapping.mapping_type == "direct_copy":
            if mapping.source_field in source_record:
                transformed[mapping.target_field] = source_record[mapping.source_field]
        elif mapping.mapping_type == "static_default":
            transformed[mapping.target_field] = mapping.static_value
        elif mapping.mapping_type == "conditional":
            # First-match-wins conditional evaluation
            conditions = mapping.conditional_config.conditions
            fallback = mapping.conditional_config.fallback
            
            matched_value = None
            for condition in conditions:
                if _match_condition(source_record, condition):
                    matched_value = condition.value
                    break
            
            if matched_value is not None:
                transformed[mapping.target_field] = matched_value
            elif fallback is not None:
                transformed[mapping.target_field] = fallback
            # else: omit field entirely (per Phase 3 pattern)
        else:
            raise ValueError(f"Unsupported mapping type: {mapping.mapping_type}")
    
    # Filter out None values per CONTEXT.md requirement
    return {k: v for k, v in transformed.items() if v is not None}
