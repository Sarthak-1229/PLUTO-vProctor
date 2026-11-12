"""TDD tests for Phase 2 authentication, token rotation, CSRF, lockout, reset, and rate limits."""
from __future__ import annotations

import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.db.database import SessionLocal
from backend.app.db.models import AuditLog, CandidateProfile, OneTimeToken, RefreshToken, User
from backend.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_rate_limiter_and_clean_users():
    from backend.app.services.security_service import reset_rate_limits, set_test_token_sink

    reset_rate_limits()
    captured_tokens = []
    set_test_token_sink(captured_tokens.append)
    yield captured_tokens
    set_test_token_sink(None)
    reset_rate_limits()


def _unique_email(prefix: str = "cand") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@Example.COM"


def test_register_candidate_hashes_password_normalizes_email_and_rejects_role_escalation(client):
    raw_email = f"  Alice.{uuid.uuid4().hex[:6]}@Example.COM  "
    resp = client.post(
        "/api/auth/register",
        json={
            "email": raw_email,
            "password": "StrongPassword!123",
            "full_name": "Alice Candidate",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["user"]["email"] == raw_email.strip().lower()
    assert body["user"]["role"] == "candidate"
    assert "password_hash" not in body["user"]

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == raw_email.strip().lower()).first()
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")
        assert user.password_hash != "StrongPassword!123"
        prof = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
        assert prof is not None
    finally:
        db.close()

    # Duplicate normalized email rejected
    dup = client.post(
        "/api/auth/register",
        json={
            "email": raw_email.strip().lower(),
            "password": "AnotherStrongPassword!123",
            "full_name": "Duplicate Alice",
        },
    )
    assert dup.status_code == 409

    # Mass-assignment attempt for role="admin" must be rejected
    esc = client.post(
        "/api/auth/register",
        json={
            "email": _unique_email("esc"),
            "password": "StrongPassword!123",
            "full_name": "Attacker",
            "role": "admin",
        },
    )
    assert esc.status_code == 422


def test_candidate_login_sets_cookies_and_separates_admin_portal(client):
    email = _unique_email("bob")
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": "BobStrongPassword!123", "full_name": "Bob Builder"},
    )
    assert reg.status_code == 201

    login = client.post(
        "/api/auth/login",
        json={"email": email.upper(), "password": "BobStrongPassword!123"},
    )
    assert login.status_code == 200, login.text
    data = login.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "candidate"
    assert "pluto_refresh_token" in login.cookies
    assert "pluto_csrf_token" in login.cookies

    # DB must store only hashed refresh token
    db = SessionLocal()
    try:
        rt = db.query(RefreshToken).filter(RefreshToken.user_id == data["user"]["id"]).first()
        assert rt is not None
        assert rt.token_hash != login.cookies["pluto_refresh_token"]
        assert len(rt.token_hash) == 64
    finally:
        db.close()

    # Candidate must NOT be allowed to authenticate through admin login endpoint
    admin_try = client.post(
        "/api/auth/admin/login",
        json={"email": email, "password": "BobStrongPassword!123"},
    )
    assert admin_try.status_code == 403


def test_admin_login_succeeds_for_admin_and_is_blocked_on_candidate_login(client):
    from backend.app.services.security_service import hash_password

    email = f"admin_{uuid.uuid4().hex[:8]}@pluto-admin.com"
    db = SessionLocal()
    try:
        admin_user = User(
            id=f"usr_{uuid.uuid4().hex[:12]}",
            email=email,
            password_hash=hash_password("AdminUltraSecret!2026"),
            full_name="Pluto Admin",
            role="admin",
            is_active=True,
            email_verified=True,
        )
        db.add(admin_user)
        db.commit()
    finally:
        db.close()

    # Admin blocked from candidate login portal
    cand_try = client.post(
        "/api/auth/login",
        json={"email": email, "password": "AdminUltraSecret!2026"},
    )
    assert cand_try.status_code in (401, 403)

    # Admin succeeds on /api/auth/admin/login
    admin_ok = client.post(
        "/api/auth/admin/login",
        json={"email": email, "password": "AdminUltraSecret!2026"},
    )
    assert admin_ok.status_code == 200
    assert admin_ok.json()["user"]["role"] == "admin"


def test_refresh_rotation_csrf_and_reuse_detection_revokes_family(client):
    email = _unique_email("rot")
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "RotatePassword!123", "full_name": "Rot User"},
    )
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "RotatePassword!123"},
    )
    assert login.status_code == 200
    old_access = login.json()["access_token"]
    old_refresh = login.cookies["pluto_refresh_token"]
    csrf = login.cookies["pluto_csrf_token"]

    # Verify initial access token works
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_access}"}).status_code == 200

    # Missing CSRF header must be rejected
    no_csrf = client.post("/api/auth/refresh")
    assert no_csrf.status_code == 403

    # Valid refresh rotates token cleanly
    refreshed = client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]
    new_refresh = refreshed.cookies["pluto_refresh_token"]
    new_csrf = refreshed.cookies["pluto_csrf_token"]
    assert new_refresh != old_refresh

    # Reusing OLD refresh token triggers family revocation and fails
    client.cookies.set("pluto_refresh_token", old_refresh)
    client.cookies.set("pluto_csrf_token", new_csrf)
    reused = client.post("/api/auth/refresh", headers={"X-CSRF-Token": new_csrf})
    assert reused.status_code == 401

    # Even the previously valid new_refresh token in that compromised family is now revoked
    client.cookies.set("pluto_refresh_token", new_refresh)
    after_compromise = client.post("/api/auth/refresh", headers={"X-CSRF-Token": new_csrf})
    assert after_compromise.status_code == 401

    # Token version incremented: outstanding access tokens are now immediately rejected
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_access}"}).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"}).status_code == 401


def test_logout_revokes_refresh_and_invalidates_access_token(client):
    email = _unique_email("logout")
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "LogoutPassword!123", "full_name": "Logout User"},
    )
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "LogoutPassword!123"},
    )
    access_token = login.json()["access_token"]
    csrf = login.cookies["pluto_csrf_token"]

    me_ok = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_ok.status_code == 200

    saved_refresh = login.cookies["pluto_refresh_token"]

    out = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}", "X-CSRF-Token": csrf},
    )
    assert out.status_code == 200

    me_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_after.status_code == 401

    # Replaying the logged-out refresh & CSRF cookies must also be rejected with 401
    client.cookies.set("pluto_refresh_token", saved_refresh)
    client.cookies.set("pluto_csrf_token", csrf)
    refresh_after = client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert refresh_after.status_code == 401


def test_forgot_reset_and_verify_email_tokens_are_hashed_expiring_single_use(
    client, reset_rate_limiter_and_clean_users
):
    captured = reset_rate_limiter_and_clean_users
    email = _unique_email("reset")
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": "InitialPassword!123", "full_name": "Reset User"},
    )
    assert reg.status_code == 201
    user_id = reg.json()["user"]["id"]

    # Verify email token captured on register
    verify_events = [t for t in captured if t["purpose"] == "email_verify" and t["user_id"] == user_id]
    assert len(verify_events) == 1
    verify_resp = client.post("/api/auth/verify-email", json={"token": verify_events[0]["raw_token"]})
    assert verify_resp.status_code == 200
    assert verify_resp.json()["email_verified"] is True

    # Forgot password response is identical for existing and non-existing accounts (anti-enumeration)
    fg_existing = client.post("/api/auth/forgot-password", json={"email": email})
    fg_missing = client.post("/api/auth/forgot-password", json={"email": "nobody@nonexistent-example.com"})
    assert fg_existing.status_code == 200
    assert fg_missing.status_code == 200
    assert fg_existing.json()["message"] == fg_missing.json()["message"]
    assert "token" not in fg_existing.json()

    reset_events = [t for t in captured if t["purpose"] == "password_reset" and t["user_id"] == user_id]
    assert len(reset_events) == 1
    raw_reset = reset_events[0]["raw_token"]

    # Stored token in DB must be hashed
    db = SessionLocal()
    try:
        row = db.query(OneTimeToken).filter(
            OneTimeToken.user_id == user_id, OneTimeToken.purpose == "password_reset"
        ).first()
        assert row is not None
        assert row.token_hash != raw_reset
    finally:
        db.close()

    # Reset password succeeds once
    rst_ok = client.post(
        "/api/auth/reset-password",
        json={"token": raw_reset, "new_password": "BrandNewPassword!456"},
    )
    assert rst_ok.status_code == 200

    # Reusing same token fails
    rst_reuse = client.post(
        "/api/auth/reset-password",
        json={"token": raw_reset, "new_password": "AnotherPassword!789"},
    )
    assert rst_reuse.status_code == 400

    # Old password fails, new password works
    old_login = client.post("/api/auth/login", json={"email": email, "password": "InitialPassword!123"})
    assert old_login.status_code == 401
    new_login = client.post("/api/auth/login", json={"email": email, "password": "BrandNewPassword!456"})
    assert new_login.status_code == 200


def test_expired_reset_token_rejected(client, reset_rate_limiter_and_clean_users):
    captured = reset_rate_limiter_and_clean_users
    email = _unique_email("expired")
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": "ExpirePassword!123", "full_name": "Expire User"},
    )
    user_id = reg.json()["user"]["id"]
    client.post("/api/auth/forgot-password", json={"email": email})
    raw_reset = [t for t in captured if t["purpose"] == "password_reset"][-1]["raw_token"]

    db = SessionLocal()
    try:
        row = db.query(OneTimeToken).filter(
            OneTimeToken.user_id == user_id, OneTimeToken.purpose == "password_reset"
        ).first()
        row.expires_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(minutes=5)
        db.commit()
    finally:
        db.close()

    resp = client.post(
        "/api/auth/reset-password",
        json={"token": raw_reset, "new_password": "ValidNewPassword!999"},
    )
    assert resp.status_code == 400


def test_login_lockout_and_rate_limiting_and_audit_logging(client):
    email = _unique_email("lock")
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "LockPassword!123", "full_name": "Lock User"},
    )
    for _ in range(5):
        r = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword!999"})
        assert r.status_code in (401, 423, 429)

    locked = client.post("/api/auth/login", json={"email": email, "password": "LockPassword!123"})
    assert locked.status_code in (423, 429)

    db = SessionLocal()
    try:
        logs = db.query(AuditLog).filter(AuditLog.action.in_(["auth.login_failed", "auth.account_locked"])).all()
        assert len(logs) >= 1
    finally:
        db.close()
