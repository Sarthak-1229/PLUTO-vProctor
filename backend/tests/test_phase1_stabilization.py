"""Regression & isolation tests for Phase 0.5 stabilization fixes."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.app.config import Settings, settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import InterviewSession, Job
from backend.app.main import app


def test_test_isolation_uses_temp_db_and_storage():
    """Verify tests never point at workspace production pluto.db or storage/."""
    prod_db = (Path(__file__).resolve().parent.parent / "app" / "pluto.db").resolve()
    prod_storage = (Path(__file__).resolve().parent.parent.parent / "storage").resolve()

    assert str(prod_db) not in settings.DATABASE_URL
    assert Path(settings.STORAGE_DIR).resolve() != prod_storage

    db = SessionLocal()
    try:
        # Seeded catalog must exist, while production user sessions must NOT leak into test DB
        assert db.query(Job).count() >= 12
        sarthak_leaks = (
            db.query(InterviewSession)
            .filter(InterviewSession.candidate_name.ilike("%Sarthak%"))
            .count()
        )
        assert sarthak_leaks == 0
    finally:
        db.close()


def test_settings_tolerates_non_boolean_debug_env(monkeypatch):
    """Host shells (IDE/Electron) often export DEBUG=WARN; Settings must not crash."""
    monkeypatch.setenv("DEBUG", "WARN")
    s_warn = Settings()
    assert s_warn.DEBUG is False

    monkeypatch.setenv("DEBUG", "INFO")
    assert Settings().DEBUG is False

    monkeypatch.setenv("DEBUG", "true")
    assert Settings().DEBUG is True

    monkeypatch.setenv("DEBUG", "False")
    assert Settings().DEBUG is False


def test_get_gaze_config_returns_valid_presets():
    """Verify GET /api/interview/config/gaze returns parsed gaze.json without NameError."""
    with TestClient(app) as client:
        resp = client.get("/api/interview/config/gaze")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("active_preset") in ("strict", "normal", "relaxed")
        assert "presets" in data and "strict" in data["presets"]


def test_app_uses_lifespan_not_deprecated_on_event():
    """Verify FastAPI app migrated startup logic from deprecated on_event to lifespan."""
    assert len(app.router.on_startup) == 0
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200


def test_question_service_caches_sentence_transformer():
    """Verify QuestionService.find_nearest_neighbors caches encoder instead of reloading per call."""
    from backend.app.services.question_service import QuestionService

    qs = QuestionService()
    calls = 0

    class DummyEncoder:
        def encode(self, text, normalize_embeddings=True):
            import numpy as np
            dim = qs.embeddings.shape[1] if qs.embeddings is not None else 384
            return np.ones(dim, dtype=np.float32)

    def fake_st(*args, **kwargs):
        nonlocal calls
        calls += 1
        return DummyEncoder()

    with patch("sentence_transformers.SentenceTransformer", side_effect=fake_st):
        res1 = qs.find_nearest_neighbors("What is TLS handshake?", k=2)
        res2 = qs.find_nearest_neighbors("Explain SQL indexing", k=2)

    assert len(res1) == 2 and len(res2) == 2
    assert calls == 1

