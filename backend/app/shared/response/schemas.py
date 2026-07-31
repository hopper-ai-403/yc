"""Canonical API response envelope.

Success:
{
  "success": true,
  "message": "",
  "data": {}
}

Error:
{
  "success": false,
  "error": {
    "code": "",
    "message": "",
    "details": {}
  }
}
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response envelope."""

    success: bool = True
    message: str = ""
    data: T


class ErrorBody(BaseModel):
    """Error payload nested under the error response."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    success: bool = False
    error: ErrorBody
