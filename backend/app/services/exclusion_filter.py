"""Exclusion filter service for asset record filtering.

Evaluates exclusion rules against merged asset records. Records matching
ANY rule (OR semantics) are excluded from field mapping, Qualys submission,
and child endpoint fan-out.
"""
import re

from app.services.path_resolver import resolve_path


class ExclusionRule:
    """Lightweight exclusion rule representation for filtering."""
    def __init__(self, source_field: str, operator: str, value: str):
        self.source_field = source_field
        self.operator = operator
        self.value = value


def _match_exclusion(record: dict, rule) -> bool:
    """Evaluate a single exclusion rule against a record.

    Returns True if the record matches the rule (should be excluded).
    Returns False if source_field is missing or value is None.

    Uses flat key lookup first (backward compat), then falls back to
    resolve_path for nested field access.
    """
    value = record.get(rule.source_field)
    if value is None:
        value = resolve_path(record, rule.source_field)

    if value is None:
        return False

    target = rule.value
    operator = rule.operator if isinstance(rule.operator, str) else rule.operator.value

    if operator == "equals":
        return str(value) == target
    elif operator == "not_equals":
        return str(value) != target
    elif operator == "contains":
        return target in str(value)
    elif operator == "starts_with":
        return str(value).startswith(target)
    elif operator == "ends_with":
        return str(value).endswith(target)
    elif operator == "regex":
        return re.search(target, str(value)) is not None
    elif operator == "in_list":
        # Split comma-separated list and strip whitespace
        list_items = [item.strip() for item in target.split(",")]
        return str(value) in list_items
    else:
        return False


def apply_exclusion_rules(
    records: list[dict], rules: list
) -> tuple[list[dict], int]:
    """Filter records using exclusion rules with OR semantics.

    If ANY rule matches a record, that record is excluded.

    Args:
        records: List of source/merged asset records.
        rules: List of exclusion rule instances to evaluate.

    Returns:
        Tuple of (passed_records, filtered_count).
    """
    if not rules:
        return records, 0

    passed: list[dict] = []
    filtered_count = 0

    for record in records:
        excluded = any(_match_exclusion(record, rule) for rule in rules)
        if excluded:
            filtered_count += 1
        else:
            passed.append(record)

    return passed, filtered_count
