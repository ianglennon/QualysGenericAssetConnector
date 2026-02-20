import enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, field_validator


class ConditionalOperator(str, enum.Enum):
    """Operators for conditional field mapping rules."""
    equals = "equals"
    not_equals = "not_equals"
    contains = "contains"
    regex = "regex"
    in_list = "in_list"


class ConditionRule(BaseModel):
    """Single condition in a conditional mapping rule."""
    operator: ConditionalOperator
    source_field: str
    target_value: str | list[str]  # list for in_list operator
    value: str  # Output value when condition matches


class ConditionalMappingConfig(BaseModel):
    """Configuration for conditional field mapping."""
    conditions: list[ConditionRule]
    fallback: str | None = None  # Used if no conditions match


class FieldMappingDirectCopy(BaseModel):
    mapping_type: Literal["direct_copy"] = "direct_copy"
    target_field: str
    source_field: str


class FieldMappingStaticDefault(BaseModel):
    mapping_type: Literal["static_default"] = "static_default"
    target_field: str
    static_value: str


class FieldMappingConditional(BaseModel):
    mapping_type: Literal["conditional"] = "conditional"
    target_field: str
    conditional_config: ConditionalMappingConfig
    
    @field_validator("conditional_config")
    @classmethod
    def validate_conditional_config(cls, v: ConditionalMappingConfig) -> ConditionalMappingConfig:
        if not v.conditions:
            raise ValueError("conditional_config.conditions must not be empty")
        return v


FieldMappingRule = Annotated[
    Union[FieldMappingDirectCopy, FieldMappingStaticDefault, FieldMappingConditional],
    Field(discriminator="mapping_type"),
]
