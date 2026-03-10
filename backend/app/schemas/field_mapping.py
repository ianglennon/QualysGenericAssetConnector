import enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, field_validator


class ConditionalOperator(str, enum.Enum):
    """Operators for conditional field mapping rules."""
    equals = "equals"
    not_equals = "not_equals"
    contains = "contains"
    starts_with = "starts_with"   # string prefix match
    ends_with = "ends_with"       # string suffix match
    regex = "regex"               # keep — existing data may use it
    in_list = "in_list"           # keep — existing data may use it


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


class FieldMappingCreate(BaseModel):
    """Schema for creating a field mapping."""
    mapping_type: Literal["direct_copy", "static_default", "conditional"]
    target_field: str
    source_field: str | None = None  # Required for direct_copy
    static_value: str | None = None  # Required for static_default
    conditions: list[ConditionRule] | None = None  # Required for conditional
    fallback: str | None = None  # Optional for conditional
    order: int = 0
    
    @field_validator("source_field")
    @classmethod
    def validate_direct_copy(cls, v: str | None, info) -> str | None:
        if info.data.get("mapping_type") == "direct_copy" and not v:
            raise ValueError("source_field required for direct_copy mapping")
        return v
    
    @field_validator("static_value")
    @classmethod
    def validate_static_default(cls, v: str | None, info) -> str | None:
        if info.data.get("mapping_type") == "static_default" and not v:
            raise ValueError("static_value required for static_default mapping")
        return v
    
    @field_validator("conditions")
    @classmethod
    def validate_conditional(cls, v: list | None, info) -> list | None:
        if info.data.get("mapping_type") == "conditional" and not v:
            raise ValueError("conditions required for conditional mapping")
        return v


class FieldMappingResponse(BaseModel):
    """Schema for field mapping API responses."""
    id: str
    connector_id: str
    mapping_type: str
    target_field: str
    source_field: str | None = None
    static_value: str | None = None
    conditions: list[dict] | None = None  # JSON from DB
    fallback: str | None = None
    order: int
    created_at: str  # ISO datetime string

    model_config = {"from_attributes": True}


class FieldDiscoveryItem(BaseModel):
    """A single discovered field from a source API response."""
    path: str
    type: str
    sample_value: Any


class DiscoverResponse(BaseModel):
    """Response body for GET /connectors/{id}/fields/discover."""
    fields: list[FieldDiscoveryItem]
    record_count: int


class QualysSchemaField(BaseModel):
    """A single Qualys CSAM target field with identity flag."""
    field: str
    is_identity: bool


class QualysSchemaResponse(BaseModel):
    """Response for GET /qualys/schema — full list of Qualys target fields."""
    fields: list[QualysSchemaField]


class BatchReplaceRequest(BaseModel):
    """Request body for PUT /connectors/{id}/mappings — replaces all mappings atomically."""
    mappings: list[FieldMappingCreate]


class BatchReplaceResponse(BaseModel):
    """Response for PUT /connectors/{id}/mappings."""
    replaced: int
    is_valid_mappings: bool
    validation_errors: list[str]
