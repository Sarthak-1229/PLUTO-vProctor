"""initial_schema

Revision ID: 866ba5fa0eae
Revises:
Create Date: 2026-10-28 16:52:18.576289

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '866ba5fa0eae'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    if context.is_offline_mode():
        return False
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    """Create initial v1 baseline tables if absent (safe on fresh DB and pre-created SQLite)."""
    if not _has_table("companies"):
        op.create_table(
            "companies",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("industry", sa.String(length=128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table("questions"):
        op.create_table(
            "questions",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column("split", sa.String(length=16), nullable=False),
            sa.Column("source_folder", sa.String(length=32), nullable=True),
            sa.Column("type", sa.String(length=32), nullable=False),
            sa.Column("spoken_ok", sa.Boolean(), nullable=False),
            sa.Column("skills", sa.JSON(), nullable=True),
            sa.Column("domain", sa.String(length=64), nullable=False),
            sa.Column("cluster_id", sa.Integer(), nullable=True),
            sa.Column("difficulty", sa.Integer(), nullable=True),
            sa.Column("expected_keywords", sa.JSON(), nullable=True),
            sa.Column("ideal_answer_summary", sa.Text(), nullable=True),
            sa.Column("est_seconds", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table("jobs"):
        op.create_table(
            "jobs",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=128), nullable=False),
            sa.Column("company", sa.String(length=128), nullable=False),
            sa.Column("company_id", sa.String(length=64), nullable=True),
            sa.Column("required_skills", sa.JSON(), nullable=True),
            sa.Column("preferred_skills", sa.JSON(), nullable=True),
            sa.Column("min_experience_years", sa.Integer(), nullable=True),
            sa.Column("education_levels", sa.JSON(), nullable=True),
            sa.Column("skill_weights", sa.JSON(), nullable=True),
            sa.Column("question_domains", sa.JSON(), nullable=True),
            sa.Column("pass_threshold", sa.Float(), nullable=True),
            sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table("sessions"):
        op.create_table(
            "sessions",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("job_id", sa.String(length=64), nullable=False),
            sa.Column("candidate_name", sa.String(length=128), nullable=True),
            sa.Column("resume_filename", sa.String(length=256), nullable=True),
            sa.Column("resume_text", sa.Text(), nullable=True),
            sa.Column("parsed_resume", sa.JSON(), nullable=True),
            sa.Column("screening_fit", sa.Float(), nullable=True),
            sa.Column("screening_status", sa.String(length=32), nullable=True),
            sa.Column("screening_details", sa.JSON(), nullable=True),
            sa.Column("interview_status", sa.String(length=32), nullable=True),
            sa.Column("video_filename", sa.String(length=256), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table("proctoring_events"):
        op.create_table(
            "proctoring_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("question_id", sa.String(length=64), nullable=True),
            sa.Column("t_start", sa.Float(), nullable=False),
            sa.Column("t_end", sa.Float(), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column("type", sa.String(length=64), nullable=False),
            sa.Column("severity", sa.String(length=32), nullable=True),
            sa.Column("points_deducted", sa.Float(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _has_table("reports"):
        op.create_table(
            "reports",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("overall_score", sa.Float(), nullable=False),
            sa.Column("grade", sa.String(length=8), nullable=True),
            sa.Column("readiness_label", sa.String(length=64), nullable=True),
            sa.Column("category_scores", sa.JSON(), nullable=True),
            sa.Column("summary", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id"),
        )

    if not _has_table("session_questions"):
        op.create_table(
            "session_questions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("question_id", sa.String(length=64), nullable=True),
            sa.Column("order_index", sa.Integer(), nullable=False),
            sa.Column("is_warmup", sa.Boolean(), nullable=True),
            sa.Column("is_follow_up", sa.Boolean(), nullable=True),
            sa.Column("custom_question_text", sa.Text(), nullable=True),
            sa.Column("transcript", sa.Text(), nullable=True),
            sa.Column("start_time_sec", sa.Float(), nullable=True),
            sa.Column("end_time_sec", sa.Float(), nullable=True),
            sa.Column("answer_score", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    """Drop initial baseline tables cleanly if empty/requested."""
    for table_name in (
        "session_questions",
        "reports",
        "proctoring_events",
        "sessions",
        "jobs",
        "questions",
        "companies",
    ):
        if context.is_offline_mode() or _has_table(table_name):
            op.drop_table(table_name)
