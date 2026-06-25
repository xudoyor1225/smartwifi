from datetime import datetime, timezone
from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    """Standardized API response wrapper."""
    success: bool = True
    data: T
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: str | None = None

class PaginatedResponse(ApiResponse[list[T]], Generic[T]):
    """Standardized paginated API response wrapper."""
    total: int
    offset: int
    limit: int
    has_more: bool

class ErrorDetail(BaseModel):
    """Detailed error information."""
    code: str
    message: str
    resolution: str | None = None

class ErrorResponse(BaseModel):
    """Standardized error response wrapper."""
    success: bool = False
    error: ErrorDetail
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: str | None = None
