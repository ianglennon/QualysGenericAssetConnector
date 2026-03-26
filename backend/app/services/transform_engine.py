import json
import re
from typing import Iterable

from app.schemas.field_mapping import FieldMappingRule, ConditionRule
from app.services.path_resolver import resolve_path


def _match_collect_filter(item: dict, f) -> bool:
    """Evaluate a collect filter condition against an array element."""
    value = resolve_path(item, f.field) if isinstance(item, dict) else item
    if value is None:
        return False
    target = f.value
    op = f.operator.value
    if op == "equals":
        return str(value) == target
    elif op == "not_equals":
        return str(value) != target
    elif op == "contains":
        return target in str(value)
    elif op == "starts_with":
        return str(value).startswith(target)
    elif op == "ends_with":
        return str(value).endswith(target)
    elif op == "regex":
        return re.search(target, str(value)) is not None
    elif op == "in_list":
        list_items = [i.strip() for i in target.split(",")]
        return str(value) in list_items
    return False


def _match_condition(record: dict, condition: ConditionRule) -> bool:
    """Evaluate a single condition against source record.

    Operators: equals, not_equals, contains, regex, in_list, starts_with, ends_with
    Returns False if source_field missing or value is None.
    """
    source_field = condition.source_field
    value = record.get(source_field)
    if value is None:
        value = resolve_path(record, source_field)
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
    elif operator == "starts_with":
        return str(value).startswith(target)
    elif operator == "ends_with":
        return str(value).endswith(target)
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
            else:
                val = resolve_path(source_record, mapping.source_field)
                if val is not None:
                    transformed[mapping.target_field] = val
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
        elif mapping.mapping_type == "collect":
            array_data = resolve_path(source_record, mapping.array_path)
            if not isinstance(array_data, list):
                continue
            if mapping.collect_filter:
                f = mapping.collect_filter
                array_data = [
                    item for item in array_data
                    if _match_collect_filter(item, f)
                ]
            if mapping.extract_field:
                values = [resolve_path(item, mapping.extract_field) for item in array_data if isinstance(item, dict)]
                values = [v for v in values if v is not None]
            else:
                values = array_data
            if mapping.separator:
                transformed[mapping.target_field] = mapping.separator.join(str(v) for v in values)
            else:
                transformed[mapping.target_field] = json.dumps(values)
        else:
            raise ValueError(f"Unsupported mapping type: {mapping.mapping_type}")

    # Filter out None values per CONTEXT.md requirement
    return {k: v for k, v in transformed.items() if v is not None}
