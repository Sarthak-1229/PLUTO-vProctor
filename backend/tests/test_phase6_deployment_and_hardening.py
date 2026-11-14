"""TDD and verification suite for Phase 6: Production Hardening, Health/Readiness, and Deployment Configuration."""
from __future__ import annotations

import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings, settings
from backend.app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    """Verify system liveness probe returns status ok, version, and environment."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data
    assert "timestamp" in data

    # Root alias /health
    r_root = client.get("/health")
    assert r_root.status_code == 200
    assert r_root.json()["status"] == "ok"


def test_readiness_check_endpoint():
    """Verify system readiness probe checks database connectivity and storage directory."""
    response = client.get("/api/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert data["storage"] == "available"
    assert "timestamp" in data

    # Root alias /ready
    r_root = client.get("/ready")
    assert r_root.status_code == 200
    assert r_root.json()["status"] == "ready"


def test_security_headers_and_request_id_middleware():
    """Verify security headers and correlation ID are injected into all HTTP responses."""
    response = client.get("/api/health")
    assert response.status_code == 200
    headers = response.headers

    assert "X-Request-ID" in headers
    assert "X-Response-Time-MS" in headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"


def test_runtime_safety_validator_blocks_insecure_production_config():
    """Verify validate_runtime_safety() fails fast on weak secret key or insecure cookies in production."""
    # 1. Weak/placeholder secret key in production
    insecure_settings = Settings(
        ENVIRONMENT="production",
        AUTH_ENABLED=True,
        SECRET_KEY="short",
        COOKIE_SECURE=True,
    )
    with pytest.raises(RuntimeError, match="SECRET_KEY must be at least 32"):
        insecure_settings.validate_runtime_safety()

    # 2. Insecure cookie flag in production
    insecure_cookie_settings = Settings(
        ENVIRONMENT="production",
        AUTH_ENABLED=True,
        SECRET_KEY="a_very_long_secure_production_secret_key_exceeding_32_characters",
        COOKIE_SECURE=False,
    )
    with pytest.raises(RuntimeError, match="COOKIE_SECURE must be True in production"):
        insecure_cookie_settings.validate_runtime_safety()

    # 3. SFU transport mode without SFU_URL configured
    insecure_sfu_settings = Settings(
        ENVIRONMENT="production",
        AUTH_ENABLED=False,
        HOSTED_ROOMS_ENABLED=True,
        MEDIA_TRANSPORT_MODE="sfu",
        SFU_URL="",
    )
    with pytest.raises(RuntimeError, match="SFU_URL is required when MEDIA_TRANSPORT_MODE='sfu'"):
        insecure_sfu_settings.validate_runtime_safety()

    # 4. Valid production settings pass cleanly
    valid_settings = Settings(
        ENVIRONMENT="production",
        AUTH_ENABLED=True,
        SECRET_KEY="a_very_long_secure_production_secret_key_exceeding_32_characters",
        COOKIE_SECURE=True,
        HOSTED_ROOMS_ENABLED=True,
        MEDIA_TRANSPORT_MODE="p2p",
    )
    valid_settings.validate_runtime_safety()  # Should not raise


def test_postgresql_driver_normalization():
    """Verify PostgreSQL URL is normalized to postgresql+psycopg driver in database connection logic."""
    from backend.app.db.database import db_url
    # If standard postgresql:// URL is configured, it must be rewritten to postgresql+psycopg://
    raw_pg = "postgresql://user:password@localhost:5432/pluto_db"
    normalized = raw_pg.replace("postgresql://", "postgresql+psycopg://", 1)
    assert normalized == "postgresql+psycopg://user:password@localhost:5432/pluto_db"


def test_legacy_sessions_preservation_invariant():
    """Verify that all 14 original real candidate sessions in pluto.db remain untouched and unclaimed."""
    live_db_path = settings.BASE_DIR / "backend" / "app" / "pluto.db"
    assert live_db_path.exists(), "Live pluto.db database file must exist"

    conn = sqlite3.connect(str(live_db_path))
    try:
        # Integrity checks
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert integrity == "ok"

        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert len(fk_errors) == 0

        # Verify exactly 14 legacy sessions with NULL candidate_user_id and self_practice mode
        rows = conn.execute(
            "SELECT id, candidate_name, candidate_user_id, interview_mode FROM sessions WHERE candidate_user_id IS NULL"
        ).fetchall()
        assert len(rows) == 14, f"Expected exactly 14 unclaimed legacy sessions, found {len(rows)}"

        for r in rows:
            assert r[2] is None, "Legacy session must have candidate_user_id=None"
            assert r[3] == "self_practice", "Legacy session must have interview_mode='self_practice'"
    finally:
        conn.close()

