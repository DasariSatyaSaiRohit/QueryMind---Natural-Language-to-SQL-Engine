from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class Connection(Base):
    __tablename__ = "connections"

    connection_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    connection_string_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    db_name: Mapped[str] = mapped_column(String(100), nullable=False)
    db_type: Mapped[str] = mapped_column(String(20), nullable=False, default="postgresql")
    table_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    class Config:
        from_attributes = True
