import re
from pydantic import BaseModel, Field, field_serializer, field_validator, ConfigDict
from typing import Optional
from datetime import datetime


VALID_PREFIXES = ("postgresql://", "postgres://", "mysql://", "sqlite://")


class ConnectionAddRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    url: str = Field(..., min_length=10, max_length=2048, description="Database connection URI")
    user_id: str = Field(..., min_length=36, max_length=36, description="UUID of the owning user")

    @field_validator("url")
    @classmethod
    def validate_connection_string(cls, v: str) -> str:
        if not any(v.startswith(p) for p in VALID_PREFIXES):
            raise ValueError(
                f"connection_string must start with one of: {', '.join(VALID_PREFIXES)}"
            )
        # Disallow obvious injection
        lower = v.lower()
        for blocked in ("; drop", "union select", "-- ", "/*", "xp_"):
            if blocked in lower:
                raise ValueError("Suspicious pattern detected in connection_string")
        return v

    @field_validator("user_id")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        if not re.match(pattern, v, re.IGNORECASE):
            raise ValueError("user_id must be a valid UUID v4")
        return v.lower()


class ConnectionResponse(BaseModel):
    connection_id: str
    user_id: str
    connection_string_encrypted: str
    db_name: str
    db_type: str
    table_count: int
    table_names: Optional[list[str]] = []
    last_accessed: Optional[datetime] = None
    created_at: datetime |None

    model_config = ConfigDict(from_attributes=True)
    @field_serializer('created_at')
    def serialize_created_at(self, v: datetime | None) -> str | None:
        return v.isoformat() if v else None
    
    @field_serializer('last_accessed')
    def serialize_last_accessed(self, v: datetime | None) -> str | None:
        return v.isoformat() if v else None


class ConnectionListResponse(BaseModel):
    connections: list[ConnectionResponse]
    total: int
