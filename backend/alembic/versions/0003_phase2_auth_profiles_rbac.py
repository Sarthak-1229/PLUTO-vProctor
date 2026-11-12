"""phase2_auth_profiles_rbac

Revision ID: 0003_phase2_auth_profiles_rbac
Revises: 0002_add_core_indexes
Create Date: 2026-11-12 18:16:00

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


revision: str = "0003_phase2_auth_profiles_rbac"
down_revision: Union[str, Sequence[str], None] = "0002_add_core_indexes"
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
    """Create Phase 2 auth, profile, resume, template, token, and audit tables plus additive session columns."""
    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=512), nullable=False),
            sa.Column("full_name", sa.String(length=128), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("email_verified", sa.Boolean(), nullable=False),
            sa.Column("failed_login_attempts", sa.Integer(), nullable=False),
            sa.Column("locked_until", sa.DateTime(), nullable=True),
            sa.Column("token_version", sa.Integer(), nullable=False),
            sa.Column("last_login_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_users_email", "users", ["email"], unique=True)
    _create_index_if_missing("ix_users_role", "users", ["role"], unique=False)

    if not _has_table("candidate_profiles"):
        op.create_table(
            "candidate_profiles",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("headline", sa.String(length=255), nullable=True),
            sa.Column("phone", sa.String(length=32), nullable=True),
            sa.Column("location", sa.String(length=128), nullable=True),
            sa.Column("education_level", sa.String(length=64), nullable=True),
            sa.Column("education_details_json", sa.JSON(), nullable=True),
            sa.Column("experience_years", sa.Float(), nullable=False),
            sa.Column("experience_summary_json", sa.JSON(), nullable=True),
            sa.Column("technical_skills_json", sa.JSON(), nullable=True),
            sa.Column("preferred_roles_json", sa.JSON(), nullable=True),
            sa.Column("portfolio_links_json", sa.JSON(), nullable=True),
            sa.Column("bio", sa.Text(), nullable=True),
            sa.Column("profile_completed", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_candidate_profiles_user_id", "candidate_profiles", ["user_id"], unique=True)

    if not _has_table("resumes"):
        op.create_table(
            "resumes",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=False),
            sa.Column("storage_key", sa.String(length=255), nullable=False),
            sa.Column("mime_type", sa.String(length=128), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=False),
            sa.Column("sha256_hash", sa.String(length=64), nullable=False),
            sa.Column("raw_text", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("storage_key"),
        )
    _create_index_if_missing("ix_resumes_user_id", "resumes", ["user_id"], unique=False)

    if not _has_table("resume_profiles"):
        op.create_table(
            "resume_profiles",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("resume_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("extracted_data_json", sa.JSON(), nullable=False),
            sa.Column("edited_data_json", sa.JSON(), nullable=True),
            sa.Column("field_provenance_json", sa.JSON(), nullable=True),
            sa.Column("confirmed_by_user", sa.Boolean(), nullable=False),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_resume_profiles_resume_id", "resume_profiles", ["resume_id"], unique=True)
    _create_index_if_missing("ix_resume_profiles_user_id", "resume_profiles", ["user_id"], unique=False)

    if not _has_table("job_role_templates"):
        op.create_table(
            "job_role_templates",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("slug", sa.String(length=128), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("level", sa.String(length=32), nullable=False),
            sa.Column("domain", sa.String(length=128), nullable=False),
            sa.Column("required_skills_json", sa.JSON(), nullable=False),
            sa.Column("preferred_skills_json", sa.JSON(), nullable=False),
            sa.Column("min_experience_years", sa.Float(), nullable=False),
            sa.Column("education_levels_json", sa.JSON(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("mapped_job_id", sa.String(length=64), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["mapped_job_id"], ["jobs.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_job_role_templates_slug", "job_role_templates", ["slug"], unique=True)

    if not _has_table("job_recommendations"):
        op.create_table(
            "job_recommendations",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("source_type", sa.String(length=32), nullable=False),
            sa.Column("target_type", sa.String(length=32), nullable=False),
            sa.Column("target_id", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("match_score", sa.Float(), nullable=False),
            sa.Column("matched_skills_json", sa.JSON(), nullable=False),
            sa.Column("missing_skills_json", sa.JSON(), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_job_recommendations_user_id", "job_recommendations", ["user_id"], unique=False)
    _create_index_if_missing("ix_job_recommendations_target_id", "job_recommendations", ["target_id"], unique=False)

    if not _has_table("refresh_tokens"):
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("rotation_family_id", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("replaced_by_id", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"], unique=False)
    _create_index_if_missing("ix_refresh_tokens_rotation_family_id", "refresh_tokens", ["rotation_family_id"], unique=False)
    _create_index_if_missing("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    _create_index_if_missing("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)

    if not _has_table("one_time_tokens"):
        op.create_table(
            "one_time_tokens",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("purpose", sa.String(length=32), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_one_time_tokens_expires_at", "one_time_tokens", ["expires_at"], unique=False)
    _create_index_if_missing("ix_one_time_tokens_purpose", "one_time_tokens", ["purpose"], unique=False)
    _create_index_if_missing("ix_one_time_tokens_token_hash", "one_time_tokens", ["token_hash"], unique=True)
    _create_index_if_missing("ix_one_time_tokens_user_id", "one_time_tokens", ["user_id"], unique=False)

    if not _has_table("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("actor_user_id", sa.String(length=64), nullable=True),
            sa.Column("actor_role", sa.String(length=32), nullable=True),
            sa.Column("action", sa.String(length=128), nullable=False),
            sa.Column("resource_type", sa.String(length=64), nullable=False),
            sa.Column("resource_id", sa.String(length=64), nullable=True),
            sa.Column("details_json", sa.JSON(), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    _create_index_if_missing("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"], unique=False)
    _create_index_if_missing("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)
    _create_index_if_missing("ix_audit_logs_resource_id", "audit_logs", ["resource_id"], unique=False)
    _create_index_if_missing("ix_audit_logs_resource_type", "audit_logs", ["resource_type"], unique=False)

    # Additive columns on existing sessions table (preserving all 14 legacy rows unclaimed)
    need_cuser = context.is_offline_mode() or not _has_column("sessions", "candidate_user_id")
    need_mode = context.is_offline_mode() or not _has_column("sessions", "interview_mode")
    need_room = context.is_offline_mode() or not _has_column("sessions", "room_id")
    if need_cuser or need_mode or need_room:
        with op.batch_alter_table("sessions", schema=None) as batch_op:
            if need_cuser:
                batch_op.add_column(sa.Column("candidate_user_id", sa.String(length=64), nullable=True))
                batch_op.create_foreign_key(
                    "fk_sessions_candidate_user_id_users",
                    "users",
                    ["candidate_user_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            if need_mode:
                batch_op.add_column(
                    sa.Column(
                        "interview_mode",
                        sa.String(length=32),
                        server_default="self_practice",
                        nullable=False,
                    )
                )
            if need_room:
                batch_op.add_column(sa.Column("room_id", sa.String(length=64), nullable=True))

    _create_index_if_missing("ix_sessions_candidate_user_id", "sessions", ["candidate_user_id"], unique=False)
    _create_index_if_missing("ix_sessions_room_id", "sessions", ["room_id"], unique=False)


def downgrade() -> None:
    """Drop Phase 2 additive columns and tables while preserving core v1 tables and rows."""
    for ix_name in ("ix_sessions_room_id", "ix_sessions_candidate_user_id"):
        if context.is_offline_mode() or _has_index("sessions", ix_name):
            op.drop_index(ix_name, table_name="sessions")

    has_cuser = context.is_offline_mode() or _has_column("sessions", "candidate_user_id")
    has_mode = context.is_offline_mode() or _has_column("sessions", "interview_mode")
    has_room = context.is_offline_mode() or _has_column("sessions", "room_id")
    if has_cuser or has_mode or has_room:
        with op.batch_alter_table("sessions", schema=None) as batch_op:
            if has_room:
                batch_op.drop_column("room_id")
            if has_mode:
                batch_op.drop_column("interview_mode")
            if has_cuser:
                batch_op.drop_constraint("fk_sessions_candidate_user_id_users", type_="foreignkey")
                batch_op.drop_column("candidate_user_id")

    for table_name in (
        "audit_logs",
        "one_time_tokens",
        "refresh_tokens",
        "job_recommendations",
        "job_role_templates",
        "resume_profiles",
        "resumes",
        "candidate_profiles",
        "users",
    ):
        if context.is_offline_mode() or _has_table(table_name):
            op.drop_table(table_name)

