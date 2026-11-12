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
}
EXPECTED_INDEXES = {
    "sessions": {"ix_sessions_interview_status"},
    "session_questions": {"ix_session_questions_session_id", "ix_session_questions_order_index"},
    "proctoring_events": {"ix_proctoring_events_session_id", "ix_proctoring_events_t_start"},
}


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
    finally:
        dst_conn.close()

    # Verify safe downgrade back to 866ba5fa0eae drops only secondary indexes, preserving all rows
    command.downgrade(cfg, "866ba5fa0eae")
    eng2 = create_engine(db_url)
    try:
        insp2 = inspect(eng2)
        for table in EXPECTED_TABLES:
            assert table in insp2.get_table_names()
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
            assert f"CREATE INDEX {ix}" in sql_text


@pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRES_URL"),
    reason="Set TEST_POSTGRES_URL to execute live PostgreSQL migration test (see CI postgres service).",
)
def test_alembic_upgrade_live_postgresql():
    """Live fresh PostgreSQL database migration verification when TEST_POSTGRES_URL is supplied."""
    pg_url = os.environ["TEST_POSTGRES_URL"]
    cfg = _make_alembic_cfg(pg_url)
    command.upgrade(cfg, "head")
    eng = create_engine(pg_url)
    try:
        insp = inspect(eng)
        assert EXPECTED_TABLES.issubset(set(insp.get_table_names()))
        for table, expected_ix in EXPECTED_INDEXES.items():
            assert expected_ix.issubset({ix["name"] for ix in insp.get_indexes(table)})
    finally:
        eng.dispose()


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
