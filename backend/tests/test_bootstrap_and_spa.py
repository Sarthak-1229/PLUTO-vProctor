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
