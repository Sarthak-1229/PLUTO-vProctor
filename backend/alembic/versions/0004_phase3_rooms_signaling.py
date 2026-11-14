"""phase3_rooms_signaling

Revision ID: 0004_phase3_rooms_signaling
Revises: 0003_phase2_auth_profiles_rbac
Create Date: 2026-11-13 16:30:00

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "0004_phase3_rooms_signaling"
down_revision: Union[str, Sequence[str], None] = "0003_phase2_auth_profiles_rbac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return None if context.is_offline_mode() else sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    insp = _insp()
    return False if insp is None else insp.has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    insp = _insp()
    if insp is None or not insp.has_table(table_name):
        return False
    return any(col.get("name") == column_name for col in insp.get_columns(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    insp = _insp()
    if insp is None or not insp.has_table(table_name):
        return False
    return any(ix.get("name") == index_name for ix in insp.get_indexes(table_name))


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    if context.is_offline_mode() or not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    """Create Phase 3 hosted rooms, participants, questions, events, and question sets."""
    # 1. question_sets
    if not _has_table("question_sets"):
        op.create_table(
            "question_sets",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("owner_admin_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("source_filename", sa.String(length=255), nullable=True),
            sa.Column("schema_version", sa.String(length=32), nullable=False, server_default="1.0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("checksum", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_question_sets_owner_admin_id", "question_sets", ["owner_admin_id"])
    _create_index_if_missing("ix_question_sets_status", "question_sets", ["status"])

    # 2. question_set_items
    if not _has_table("question_set_items"):
        op.create_table(
            "question_set_items",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("question_set_id", sa.String(length=64), sa.ForeignKey("question_sets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_question_id", sa.String(length=64), nullable=True),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("domain", sa.String(length=128), nullable=False, server_default="General"),
            sa.Column("difficulty", sa.String(length=32), nullable=False, server_default="Intermediate"),
            sa.Column("target_skills_json", sa.JSON(), nullable=False),
            sa.Column("ideal_criteria_json", sa.JSON(), nullable=False),
            sa.Column("ordinal", sa.Integer(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_question_set_items_question_set_id", "question_set_items", ["question_set_id"])
    _create_index_if_missing("ix_question_set_items_ordinal", "question_set_items", ["ordinal"])

    # 3. interview_rooms
    if not _has_table("interview_rooms"):
        op.create_table(
            "interview_rooms",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("created_by_admin_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("assigned_candidate_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("room_code_hash", sa.String(length=64), nullable=False),
            sa.Column("invite_token_hash", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
            sa.Column("scheduled_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="3600"),
            sa.Column("mode", sa.String(length=32), nullable=False, server_default="hosted"),
            sa.Column("proctoring_preset", sa.String(length=32), nullable=False, server_default="strict"),
            sa.Column("current_sequence_version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("current_question_ordinal", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("question_set_id", sa.String(length=64), sa.ForeignKey("question_sets.id", ondelete="SET NULL"), nullable=True),
            sa.Column("active_session_id", sa.String(length=64), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_interview_rooms_created_by_admin_id", "interview_rooms", ["created_by_admin_id"])
    _create_index_if_missing("ix_interview_rooms_assigned_candidate_id", "interview_rooms", ["assigned_candidate_id"])
    _create_index_if_missing("ix_interview_rooms_room_code_hash", "interview_rooms", ["room_code_hash"])
    _create_index_if_missing("ix_interview_rooms_invite_token_hash", "interview_rooms", ["invite_token_hash"])
    _create_index_if_missing("ix_interview_rooms_status", "interview_rooms", ["status"])
    _create_index_if_missing("ix_interview_rooms_scheduled_at", "interview_rooms", ["scheduled_at"])
    _create_index_if_missing("ix_interview_rooms_expires_at", "interview_rooms", ["expires_at"])
    _create_index_if_missing("ix_interview_rooms_active_session_id", "interview_rooms", ["active_session_id"])

    # 4. room_participants
    if not _has_table("room_participants"):
        op.create_table(
            "room_participants",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("room_id", sa.String(length=64), sa.ForeignKey("interview_rooms.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False, server_default="candidate"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="invited"),
            sa.Column("joined_at", sa.DateTime(), nullable=True),
            sa.Column("left_at", sa.DateTime(), nullable=True),
            sa.Column("reconnect_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("device_checks_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_room_participants_room_id", "room_participants", ["room_id"])
    _create_index_if_missing("ix_room_participants_user_id", "room_participants", ["user_id"])

    # 5. room_questions
    if not _has_table("room_questions"):
        op.create_table(
            "room_questions",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("room_id", sa.String(length=64), sa.ForeignKey("interview_rooms.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_question_id", sa.String(length=64), nullable=True),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("domain", sa.String(length=128), nullable=False, server_default="General"),
            sa.Column("difficulty", sa.String(length=32), nullable=False, server_default="Intermediate"),
            sa.Column("target_skills_json", sa.JSON(), nullable=False),
            sa.Column("ideal_criteria_json", sa.JSON(), nullable=False),
            sa.Column("ordinal", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("time_limit_seconds", sa.Integer(), nullable=False, server_default="180"),
            sa.Column("asked_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_room_questions_room_id", "room_questions", ["room_id"])
    _create_index_if_missing("ix_room_questions_ordinal", "room_questions", ["ordinal"])

    # 6. room_events
    if not _has_table("room_events"):
        op.create_table(
            "room_events",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("room_id", sa.String(length=64), sa.ForeignKey("interview_rooms.id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_user_id", sa.String(length=64), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("payload_json_redacted", sa.JSON(), nullable=True),
            sa.Column("sequence_no", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_room_events_room_id", "room_events", ["room_id"])
    _create_index_if_missing("ix_room_events_actor_user_id", "room_events", ["actor_user_id"])
    _create_index_if_missing("ix_room_events_event_type", "room_events", ["event_type"])
    _create_index_if_missing("ix_room_events_sequence_no", "room_events", ["sequence_no"])
    _create_index_if_missing("ix_room_events_created_at", "room_events", ["created_at"])


def downgrade() -> None:
    """Drop Phase 3 room orchestration and question set tables in reverse dependency order."""
    insp = _insp()
    for tbl in [
        "room_events",
        "room_questions",
        "room_participants",
        "interview_rooms",
        "question_set_items",
        "question_sets",
    ]:
        if insp is not None and insp.has_table(tbl):
            op.drop_table(tbl)

