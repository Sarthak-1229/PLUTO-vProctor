"""TDD tests for Phase 1 environment validation, feature flags, and standardized API errors."""
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.config import Settings
from backend.app.main import RequestIDMiddleware, app


def test_feature_flags_and_transport_defaults():
    """Verify v2 feature flags default safely so offline self-practice remains default."""
    s = Settings()
    assert s.AUTH_ENABLED is False
    assert s.HOSTED_ROOMS_ENABLED is False
    assert s.LIVE_MEDIA_ENABLED is False
    assert s.MEDIA_TRANSPORT_MODE == "p2p"
    assert isinstance(s.STUN_SERVERS, list) and len(s.STUN_SERVERS) >= 1
    assert s.TURN_SERVER_URLS == []
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert s.REFRESH_TOKEN_EXPIRE_DAYS == 7
    assert s.COOKIE_SECURE is False
    s.validate_runtime_safety()


def test_turn_server_urls_parses_csv_and_json():
    """Verify comma-separated env values and list inputs both parse cleanly."""
    s_csv = Settings(TURN_SERVER_URLS="turn:turn1.example.com:3478, turns:turn2.example.com:5349")
    assert s_csv.TURN_SERVER_URLS == [
        "turn:turn1.example.com:3478",
        "turns:turn2.example.com:5349",
    ]
    s_empty = Settings(TURN_SERVER_URLS="   ")
    assert s_empty.TURN_SERVER_URLS == []


def test_scoring_weights_and_numeric_bounds_validated():
    """Reject out-of-range ports, non-positive timeouts, and unbalanced scoring weights."""
    with pytest.raises((ValidationError, ValueError)):
        Settings(API_PORT=70000)

    with pytest.raises((ValidationError, ValueError)):
        Settings(LLM_TIMEOUT_SECONDS=0)

    with pytest.raises((ValidationError, ValueError)):
        Settings(
            SCORING_WEIGHTS={
                "technical_depth": 0.9,
                "communication": 0.9,
                "proctoring_integrity": 0.1,
                "resume_relevance": 0.1,
            }
        )


def test_validate_runtime_safety_blocks_insecure_production():
    """Production runtime with enabled auth or SFU requires strong secret / endpoint."""
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings(ENVIRONMENT="production", AUTH_ENABLED=True, SECRET_KEY="too-short").validate_runtime_safety()

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            AUTH_ENABLED=True,
            SECRET_KEY="change-me-in-production-placeholder-value",
        ).validate_runtime_safety()

    with pytest.raises(RuntimeError, match="SFU_URL"):
        Settings(
            ENVIRONMENT="production",
            HOSTED_ROOMS_ENABLED=True,
            MEDIA_TRANSPORT_MODE="sfu",
            SFU_URL="",
        ).validate_runtime_safety()

    # Valid production config should succeed
    Settings(
        ENVIRONMENT="production",
        AUTH_ENABLED=True,
        SECRET_KEY="a" * 48,
        HOSTED_ROOMS_ENABLED=True,
        MEDIA_TRANSPORT_MODE="p2p",
    ).validate_runtime_safety()


def test_environment_normalization_and_invalid_value_rejected():
    """ENVIRONMENT normalizes blank/alias values cleanly and rejects typos."""
    assert Settings(ENVIRONMENT="").ENVIRONMENT == "development"
    assert Settings(ENVIRONMENT="  PROD  ").ENVIRONMENT == "production"
    assert Settings(ENVIRONMENT="testing").ENVIRONMENT == "test"

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings(ENVIRONMENT="  PROD  ", AUTH_ENABLED=True, SECRET_KEY="").validate_runtime_safety()

    with pytest.raises((ValidationError, ValueError)):
        Settings(ENVIRONMENT="producton")


def test_http_exception_returns_standardized_error_envelope():
    """404 HTTPException retains detail and adds structured error metadata with request_id."""
    with TestClient(app) as client:
        resp = client.get(
            "/api/interview/nonexistent_phase1_sid",
            headers={"X-Request-ID": "req-404-check"},
        )
    assert resp.status_code == 404
    body = resp.json()
    assert "detail" in body
    assert body["error"]["code"] == "HTTP_404"
    assert body["error"]["message"] == body["detail"]
    assert body["error"]["request_id"] == "req-404-check"
    assert resp.headers.get("X-Request-ID") == "req-404-check"


def test_validation_error_returns_standardized_422_envelope():
    """RequestValidationError returns structured 422 payload preserving detail and request_id."""
    with TestClient(app) as client:
        resp = client.put(
            "/api/settings",
            json={"speech_pause_sec": "not-a-float"},
            headers={"X-Request-ID": "req-422-check"},
        )
    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["request_id"] == "req-422-check"
    assert isinstance(body["error"]["details"], list)
    assert len(body["error"]["details"]) >= 1
    assert resp.headers.get("X-Request-ID") == "req-422-check"


def test_unhandled_exception_returns_sanitized_500_envelope(caplog):
    """Unhandled exceptions return sanitized 500 JSON with CORS, security headers, and correlated logs."""
    from fastapi.middleware.cors import CORSMiddleware
    from backend.app.core.errors import register_exception_handlers

    mini = FastAPI()
    mini.add_middleware(RequestIDMiddleware)
    mini.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(mini, cors_origins=["http://localhost:5173"])

    @mini.get("/boom")
    def boom(request: Request):
        raise RuntimeError("postgresql://secret_password_should_not_leak")

    @mini.get("/custom-http")
    def custom_http():
        raise HTTPException(status_code=403, detail="Forbidden resource")

    with caplog.at_level("ERROR", logger="pluto.errors"):
        with TestClient(mini, raise_server_exceptions=False) as client:
            resp = client.get(
                "/boom",
                headers={"X-Request-ID": "req-500-check", "Origin": "http://localhost:5173"},
            )
            assert resp.status_code == 500
            body = resp.json()
            assert "secret_password_should_not_leak" not in resp.text
            assert body["error"]["code"] == "INTERNAL_ERROR"
            assert body["error"]["request_id"] == "req-500-check"
            assert resp.headers.get("X-Request-ID") == "req-500-check"
            assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
            assert resp.headers.get("Access-Control-Allow-Credentials") == "true"
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"
            assert resp.headers.get("X-Frame-Options") == "DENY"
            assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
            assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

            disallowed = client.get(
                "/boom",
                headers={"X-Request-ID": "req-500-evil", "Origin": "https://evil.example"},
            )
            assert disallowed.status_code == 500
            assert "access-control-allow-origin" not in disallowed.headers

            resp_403 = client.get("/custom-http")
            assert resp_403.status_code == 403
            assert resp_403.json()["error"]["code"] == "HTTP_403"

    error_records = [rec for rec in caplog.records if rec.name == "pluto.errors"]
    assert error_records, "Expected pluto.errors log record for unhandled 500"
    assert getattr(error_records[0], "request_id", None) == "req-500-check"

