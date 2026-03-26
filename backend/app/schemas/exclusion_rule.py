from pydantic import BaseModel
from app.schemas.field_mapping import ConditionalOperator


class ExclusionRule(BaseModel):
    """A single exclusion rule that filters records from pipeline processing.

    Rules evaluate against the merged asset record. If a record matches,
    it is excluded from field mapping, Qualys submission, and child fan-out.
    """
    source_field: str
    operator: ConditionalOperator
    value: str  # target value to match against
