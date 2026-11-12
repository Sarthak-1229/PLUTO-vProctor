"""TDD tests for Alembic initial schema, secondary index migrations, dual-DB compatibility, and UTC timestamps."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import os
import shutil
import sqlite3
import warnings
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from backend.app.services.report_service import ReportService

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ALEMBIC_INI = ROOT_DIR / "alembic.ini"
PROD_DB = ROOT_DIR / "backend" / "app" / "pluto.db"

EXPECTED_TABLES = {
    "companies",
    "jobs",
    "questions",
    "sessions",
    "session_questions",
    "proctoring_events",
    "reports",
    "users",
    "candidate_profiles",
    "resumes",
    "resume_profiles",
    "job_role_templates",
    "job_recommendations",
    "refresh_tokens",
    "one_time_tokens",
    "audit_logs",
}
EXPECTED_INDEXES = {
    "sessions": {"ix_sessions_interview_status", "ix_sessions_candidate_user_id", "ix_sessions_room_id"},
    "session_questions": {"ix_session_questions_session_id", "ix_session_questions_order_index"},
    "proctoring_events": {"ix_proctoring_events_session_id", "ix_proctoring_events_t_start"},
    "users": {"ix_users_email", "ix_users_role"},
    "resumes": {"ix_resumes_user_id"},
    "resume_profiles": {"ix_resume_profiles_user_id"},
    "job_recommendations": {"ix_job_recommendations_user_id", "ix_job_recommendations_target_id"},
    "refresh_tokens": {"ix_refresh_tokens_user_id", "ix_refresh_tokens_rotation_family_id", "ix_refresh_tokens_expires_at"},
    "one_time_tokens": {"ix_one_time_tokens_user_id", "ix_one_time_tokens_purpose", "ix_one_time_tokens_expires_at"},
    "audit_logs": {"ix_audit_logs_actor_user_id", "ix_audit_logs_action", "ix_audit_logs_resource_type", "ix_audit_logs_resource_id", "ix_audit_logs_created_at"},
}
EXPECTED_SESSION_V2_COLUMNS = {"candidate_user_id", "interview_mode", "room_id"}


def _make_alembic_cfg(db_url: str, output_buf: io.StringIO | None = None) -> Config:
    cfg = Config(str(ALEMBIC_INI), stdout=output_buf) if output_buf is not None else Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_alembic_upgrade_fresh_sqlite_creates_all_tables_and_indexes(tmp_path):
    """Running alembic upgrade head on an empty SQLite DB creates all 7 tables and core indexes."""
    fresh_db = tmp_path / "fresh_sqlite.db"
    db_url = f"sqlite:///{fresh_db.as_posix()}"
    cfg = _make_alembic_cfg(db_url)

    command.upgrade(cfg, "head")
    command.check(cfg)

    eng = create_engine(db_url)
    try:
        insp = inspect(eng)
        tables = set(insp.get_table_names())
        assert EXPECTED_TABLES.issubset(tables)
        assert "alembic_version" in tables

        for table, expected_ix in EXPECTED_INDEXES.items():
            actual_ix = {ix["name"] for ix in insp.get_indexes(table)}
            assert expected_ix.issubset(actual_ix), f"{table} missing indexes: {expected_ix - actual_ix}"

        session_cols = {c["name"] for c in insp.get_columns("sessions")}
        assert EXPECTED_SESSION_V2_COLUMNS.issubset(session_cols)
    finally:
        eng.dispose()


def test_alembic_explicit_sqlalchemy_url_overrides_env_override(tmp_path, monkeypatch):
    """Explicit cfg sqlalchemy.url (used by per-DB tests) takes precedence over ALEMBIC_DATABASE_URL."""
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", "postgresql://bad:bad@127.0.0.1:5999/nonexistent?connect_timeout=1")
    fresh_db = tmp_path / "explicit_override.db"
    db_url = f"sqlite:///{fresh_db.as_posix()}"
    cfg = _make_alembic_cfg(db_url)
    command.upgrade(cfg, "head")
    eng = create_engine(db_url)
    try:
        assert EXPECTED_TABLES.issubset(set(inspect(eng).get_table_names()))
    finally:
        eng.dispose()


def test_alembic_upgrade_copy_of_existing_pluto_db_preserves_data_and_adds_indexes(tmp_path):
    """Upgrading a copy of existing stamped pluto.db adds indexes cleanly with zero data loss."""
    assert PROD_DB.exists()
    copied_db = tmp_path / "copy_pluto.db"
    shutil.copy2(PROD_DB, copied_db)

    src_conn = sqlite3.connect(str(copied_db))
    pre_tables = {
        r[0]: src_conn.execute(f"SELECT COUNT(*) FROM [{r[0]}]").fetchone()[0]
        for r in src_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    }
    pre_sids = sorted(r[0] for r in src_conn.execute("SELECT id FROM sessions").fetchall())
    src_conn.close()

    db_url = f"sqlite:///{copied_db.as_posix()}"
    cfg = _make_alembic_cfg(db_url)
    command.upgrade(cfg, "head")

    # Verify idempotent re-run at head
    command.upgrade(cfg, "head")
    command.check(cfg)

    eng = create_engine(db_url)
    try:
        insp = inspect(eng)
        for table, expected_ix in EXPECTED_INDEXES.items():
            actual_ix = {ix["name"] for ix in insp.get_indexes(table)}
            assert expected_ix.issubset(actual_ix), f"{table} missing indexes after upgrade"
    finally:
        eng.dispose()

    dst_conn = sqlite3.connect(str(copied_db))
    try:
        for t, count in pre_tables.items():
            if t == "alembic_version":
                continue
            assert dst_conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0] == count
        post_sids = sorted(r[0] for r in dst_conn.execute("SELECT id FROM sessions").fetchall())
        assert post_sids == pre_sids
        legacy_rows = dst_conn.execute(
            "SELECT candidate_user_id, interview_mode FROM sessions"
        ).fetchall()
        assert len(legacy_rows) == len(pre_sids)
        assert all(row[0] is None and row[1] == "self_practice" for row in legacy_rows)
    finally:
        dst_conn.close()

    # Verify safe downgrade back to 0002_add_core_indexes drops only Phase 2 schema while preserving legacy sessions
    command.downgrade(cfg, "0002_add_core_indexes")
    eng2 = create_engine(db_url)
    try:
        insp2 = inspect(eng2)
        for table in {"companies", "jobs", "questions", "sessions", "session_questions", "proctoring_events", "reports"}:
            assert table in insp2.get_table_names()
        assert "users" not in insp2.get_table_names()
    finally:
        eng2.dispose()


def test_alembic_postgresql_ddl_compilation_clean():
    """Verify Alembic offline --sql mode compiles valid PostgreSQL DDL for all tables and indexes."""
    buf = io.StringIO()
    cfg = _make_alembic_cfg("postgresql://pluto_user:pluto_password@localhost:5432/pluto_db", output_buf=buf)
    with redirect_stdout(buf):
        command.upgrade(cfg, "head", sql=True)

    sql_text = buf.getvalue()
    assert len(sql_text.strip()) > 0
    for table in EXPECTED_TABLES:
        assert f"CREATE TABLE {table}" in sql_text
    for expected_ix_set in EXPECTED_INDEXES.values():
        for ix in expected_ix_set:
            assert (f"CREATE INDEX {ix}" in sql_text) or (f"CREATE UNIQUE INDEX {ix}" in sql_text)


@pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRES_URL"),
    reason="Set TEST_POSTGRES_URL to execute live PostgreSQL migration test (see CI postgres service).",
)
def test_alembic_upgrade_live_postgresql():
    """Live fresh PostgreSQL database migration verification when TEST_POSTGRES_URL is supplied."""
    pg_url = os.environ["TEST_POSTGRES_URL"]
    cfg = _make_alembic_cfg(pg_url)
    command.upgrade(cfg, "head")
    command.check(cfg)
    eng = create_engine(pg_url)
    try:
        insp = inspect(eng)
        assert EXPECTED_TABLES.issubset(set(insp.get_table_names()))
        for table, expected_ix in EXPECTED_INDEXES.items():
            assert expected_ix.issubset({ix["name"] for ix in insp.get_indexes(table)})
    finally:
        eng.dispose()

    # Verify bidirectional downgrade/re-upgrade works cleanly on live PostgreSQL
    command.downgrade(cfg, "866ba5fa0eae")
    command.upgrade(cfg, "head")
    command.check(cfg)


def test_no_utcnow_deprecation_warnings_in_pdf_report():
    """Report PDF generation must use timezone-aware UTC instead of deprecated datetime.utcnow()."""
    svc = ReportService()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pdf = svc.generate_pdf_report({
            "session_id": "sess_test_utc",
            "candidate_name": "Candidate",
            "job_title": "Engineer",
            "company": "PLUTO",
            "overall_score": 80.0,
            "grade": "B",
            "readiness_label": "Ready",
            "category_scores": {"technical_depth": 80.0},
            "summary": {"executive_summary": "Good.", "strengths": ["Clear"], "concrete_tips": ["Practice"]},
        })
    assert pdf.startswith(b"%PDF")
    utc_warns = [w for w in caught if "utcnow" in str(w.message)]
    assert utc_warns == []
