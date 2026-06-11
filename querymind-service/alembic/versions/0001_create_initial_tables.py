"""create initial tables

Revision ID: 0001
Revises:
Create Date: 2024-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── connections ──────────────────────────────────────────────────────────
    op.create_table(
        "connections",
        sa.Column("connection_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("connection_string_encrypted", sa.Text(), nullable=False),
        sa.Column("db_name", sa.String(length=100), nullable=False),
        sa.Column("db_type", sa.String(length=20), nullable=False, server_default="postgresql"),
        sa.Column("table_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("last_accessed", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("connection_id"),
    )
    op.create_index("idx_connections_user_id", "connections", ["user_id"], unique=False)

    # ── query_history ────────────────────────────────────────────────────────
    op.create_table(
        "query_history",
        sa.Column("history_id", sa.String(length=32), nullable=False),
        sa.Column("session_id", sa.String(length=32), nullable=False),
        sa.Column("user_input", sa.Text(), nullable=False),
        sa.Column("sql_query", sa.Text(), nullable=False),
        sa.Column("chain_of_thought", sa.JSON(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("cache_hit", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("correlation_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("history_id"),
    )
    op.create_index("idx_query_history_session_id", "query_history", ["session_id"], unique=False)
    op.create_index(
        "idx_query_history_created_at", "query_history", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_table("query_history")
    op.drop_table("connections")
