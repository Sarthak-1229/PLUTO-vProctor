"""add_core_indexes

Revision ID: 0002_add_core_indexes
Revises: 866ba5fa0eae
Create Date: 2026-11-12 00:36:00

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = '0002_add_core_indexes'
down_revision: Union[str, Sequence[str], None] = '866ba5fa0eae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    ("ix_sessions_interview_status", "sessions", ["interview_status"]),
    ("ix_session_questions_session_id", "session_questions", ["session_id"]),
    ("ix_session_questions_order_index", "session_questions", ["order_index"]),
    ("ix_proctoring_events_session_id", "proctoring_events", ["session_id"]),
    ("ix_proctoring_events_t_start", "proctoring_events", ["t_start"]),
]


def _has_index(table_name: str, index_name: str) -> bool:
    if context.is_offline_mode():
        return False
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table_name):
        return False
    return any(ix.get("name") == index_name for ix in insp.get_indexes(table_name))


def upgrade() -> None:
    """Add missing secondary indexes on session lifecycle, questions, and proctoring events."""
    for idx_name, table_name, cols in _INDEXES:
        if not _has_index(table_name, idx_name):
            op.create_index(idx_name, table_name, cols, unique=False)


def downgrade() -> None:
    """Drop only secondary indexes added in this revision without altering table data."""
    for idx_name, table_name, _ in reversed(_INDEXES):
        if context.is_offline_mode() or _has_index(table_name, idx_name):
            op.drop_index(idx_name, table_name=table_name)

