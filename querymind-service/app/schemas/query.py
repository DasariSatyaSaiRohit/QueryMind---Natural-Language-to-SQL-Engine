import re
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Any, Optional


class QueryAskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    session_id: str = Field(..., min_length=32, max_length=32, description="Active session ID")
    question: str = Field(..., min_length=3, max_length=2000, description="Natural-language question")
    page: int = Field(default=1, ge=1, le=1000)
    page_size: int = Field(default=50, ge=1, le=200)

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]{32}$", v):
            raise ValueError("session_id must be 32 alphanumeric/dash/underscore chars")
        return v

    @field_validator("question")
    @classmethod
    def sanitize_question(cls, v: str) -> str:
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
        return cleaned.strip()


class ValidationInfo(BaseModel):
    passed: bool
    failed_checks: list[str]
    reason: str
    invalid_references: list[str]
    injection_detected: bool


class PaginationInfo(BaseModel):
    page: int
    page_size: int
    total_rows: int
    total_pages: int
    has_next: bool
    has_prev: bool


class QueryAskResponse(BaseModel):
    success: bool
    correlation_id: Optional[str]
    history_persisted: str
    data: dict[str, Any]


class SchemaIntrospectRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    session_id: str = Field(..., min_length=32, max_length=32)
    connection_id: str = Field(..., min_length=32, max_length=36)

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]{32}$", v):
            raise ValueError("Invalid session_id")
        return v
