from typing import Literal, Annotated, Union, Optional
from pydantic import BaseModel, Field


class CursorPagination(BaseModel):
    strategy: Literal["cursor"] = "cursor"
    cursor_field: str        # response field containing the next cursor value
    cursor_param: str        # query param name to send cursor
    page_size: Optional[int] = None


class OffsetLimitPagination(BaseModel):
    strategy: Literal["offset_limit"] = "offset_limit"
    offset_param: str = "offset"
    limit_param: str = "limit"
    page_size: Optional[int] = None


class LinkHeaderPagination(BaseModel):
    strategy: Literal["link_header"] = "link_header"
    # Follows RFC 5988 Link header; no extra fields needed


class PageNumberPagination(BaseModel):
    strategy: Literal["page_number"] = "page_number"
    page_param: str = "page"
    page_size_param: str = "page_size"
    page_size: Optional[int] = None


PaginationStrategy = Annotated[
    Union[CursorPagination, OffsetLimitPagination, LinkHeaderPagination, PageNumberPagination],
    Field(discriminator="strategy")
]
