from datetime import datetime
from sqlalchemy import String, Text, Integer, Boolean, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


class QueryHistory(Base):
    __tablename__ = "query_history"

    history_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    sql_query: Mapped[str] = mapped_column(Text, nullable=False)
    chain_of_thought: Mapped[list | None] = mapped_column(JSON, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())