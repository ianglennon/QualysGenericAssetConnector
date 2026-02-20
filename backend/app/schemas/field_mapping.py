from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class FieldMappingDirectCopy(BaseModel):
    mapping_type: Literal["direct_copy"] = "direct_copy"
    target_field: str
    source_field: str


class FieldMappingStaticDefault(BaseModel):
    mapping_type: Literal["static_default"] = "static_default"
    target_field: str
    static_value: str


FieldMappingRule = Annotated[
    Union[FieldMappingDirectCopy, FieldMappingStaticDefault],
    Field(discriminator="mapping_type"),
]
