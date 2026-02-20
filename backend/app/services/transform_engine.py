from typing import Iterable

from app.schemas.field_mapping import FieldMappingRule


def apply_mappings(source_record: dict, mappings: Iterable[FieldMappingRule]) -> dict:
    transformed: dict = {}
    for mapping in mappings:
        if mapping.mapping_type == "direct_copy":
            if mapping.source_field in source_record:
                transformed[mapping.target_field] = source_record[mapping.source_field]
        elif mapping.mapping_type == "static_default":
            transformed[mapping.target_field] = mapping.static_value
        else:
            raise ValueError(f"Unsupported mapping type: {mapping.mapping_type}")
    return transformed
