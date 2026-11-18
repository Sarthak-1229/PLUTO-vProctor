"""Tests for idempotent startup database seeding, admin bootstrap, and SPA fallback routing."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import settings
from backend.app.db.bootstrap import _ensure_bootstrap_admin, _seed_jobs_and_companies, _seed_questions
from backend.app.db.database import Base
from backend.app.db.models import Company, Job, Question, User


def _make_memory_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session()


def test_seed_jobs_companies_and_questions_idempotent():
    db = _make_memory_db()
    try:
        first = _seed_jobs_and_companies(db)
        assert first["companies"] > 0
        assert first["jobs"] > 0

        second = _seed_jobs_and_companies(db)
        assert second["companies"] == 0
        assert second["jobs"] == 0

        q_first = _seed_questions(db)
        assert q_first > 100
        q_second = _seed_questions(db)
        assert q_second == 0

        assert db.query(Company).count() == first["companies"]
        assert db.query(Job).count() == first["jobs"]
        assert db.query(Question).count() == q_first
    finally:
        db.close()


def test_ensure_bootstrap_admin_is_idempotent(monkeypatch):
    db = _make_memory_db()
    try:
        monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_EMAIL", "owner@pluto.example")
        monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_PASSWORD", "PlutoAdmin#2026!")
        monkeypatch.setattr(settings, "BOOTSTRAP_ADMIN_NAME", "PLUTO Owner")

        assert _ensure_bootstrap_admin(db) is True
        admin = db.query(User).filter(User.email == "owner@pluto.example").first()
        assert admin is not None
        assert admin.role == "super_admin"
        assert admin.token_version == 0

        # Second call with same credentials must be a no-op (preserve token_version)
        assert _ensure_bootstrap_admin(db) is False
        db.refresh(admin)
        assert admin.token_version == 0
    finally:
        db.close()


def test_native_catalyst_sdk_stratus_and_mail_hooks(monkeypatch):
    from unittest.mock import MagicMock
    from backend.app.services import catalyst_context, catalyst_mail
    from backend.app.services.storage_service import StorageService

    mock_bucket = MagicMock()
    mock_bucket.put_object.return_value = True
    mock_bucket.get_object.return_value = b"SQLite format 3\x00test"
    mock_email = MagicMock()

    mock_app = MagicMock()
    mock_app.stratus.return_value.bucket.return_value = mock_bucket
    mock_app.email.return_value = mock_email

    monkeypatch.setattr(settings, "STRATUS_BUCKET", "pluto-vproctor-storage")
    monkeypatch.setattr(settings, "STRATUS_ENDPOINT", "")
    monkeypatch.setattr(settings, "STRATUS_ACCESS_KEY", "")
    monkeypatch.setattr(settings, "CATALYST_MAIL_FROM", "noreply@pluto-vproctor.example")
    monkeypatch.setattr("backend.app.services.storage_service.get_catalyst_app", lambda scope="admin": mock_app)
    monkeypatch.setattr("backend.app.services.catalyst_mail.get_catalyst_app", lambda scope="admin": mock_app)

    svc = StorageService()
    assert svc.is_sdk_stratus_enabled() is True
    assert svc.upload_raw_bytes("db_snapshots/pluto.db", b"SQLite format 3\x00data") is True
    mock_bucket.put_object.assert_called_once()
    assert svc.download_raw_bytes("db_snapshots/pluto.db") == b"SQLite format 3\x00test"

    sent = catalyst_mail.send_catalyst_token_email(
        {"purpose": "password_reset", "email": "cand@example.com", "raw_token": "tok_abc123456789012345"}
    )
    assert sent is True
    mock_email.send_mail.assert_called_once()
    mail_arg = mock_email.send_mail.call_args[0][0]
    assert mail_arg["from_email"] == "noreply@pluto-vproctor.example"
    assert mail_arg["to_email"] == ["cand@example.com"]

    assert catalyst_context.capture_catalyst_headers({"x-zc-projectid": "73453000000046001", "x-zc-project-key": "k"}) is True

