"""TDD tests for Phase 2 admin bootstrap CLI, legacy session claiming, RBAC, and audit trail."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import AuditLog, InterviewSession, User
from backend.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_limits():
    from backend.app.services.security_service import reset_rate_limits

    reset_rate_limits()
    yield
    reset_rate_limits()


def test_registering_matching_name_never_auto_claims_legacy_sessions(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)

    legacy_sid = f"sess_legacy_{uuid.uuid4().hex[:10]}"
    db = SessionLocal()
    try:
        db.add(
            InterviewSession(
                id=legacy_sid,
                job_id="job_sec_analyst",
                candidate_user_id=None,
                candidate_name="Sarthak Bhosale",
                interview_status="EVALUATED",
                interview_mode="self_practice",
            )
        )
        db.commit()
    finally:
        db.close()

    email = f"sarthak.bhosale_{uuid.uuid4().hex[:6]}@example.com"
    reg = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "SarthakStrongPass!123",
            "full_name": "Sarthak Bhosale",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Candidate must NOT auto-own legacy session
    db = SessionLocal()
    try:
        sess = db.query(InterviewSession).filter(InterviewSession.id == legacy_sid).first()
        assert sess is not None
        assert sess.candidate_user_id is None
    finally:
        db.close()

    hist = client.get("/api/candidate/history", headers=headers)
    assert hist.status_code == 200
    assert all(s["session_id"] != legacy_sid for s in hist.json()["sessions"])
    assert client.get(f"/api/interview/{legacy_sid}", headers=headers).status_code == 403


def test_admin_bootstrap_cli_creates_admin_and_blocks_candidates_from_admin_routes(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    from backend.app.services.admin_bootstrap import bootstrap_admin_user

    admin_email = f"boot_admin_{uuid.uuid4().hex[:6]}@pluto-admin.com"
    db = SessionLocal()
    try:
        user = bootstrap_admin_user(
            db,
            email=admin_email,
            password="BootstrapAdmin!2026",
            full_name="Bootstrap Super Admin",
            role="super_admin",
        )
        assert user.role == "super_admin"
        assert user.email_verified is True
        assert user.password_hash.startswith("$argon2id$")
    finally:
        db.close()

    # Register normal candidate and verify /api/admin/* returns 403
    cand_resp = client.post(
        "/api/auth/register",
        json={
            "email": f"cand_{uuid.uuid4().hex[:6]}@example.com",
            "password": "CandidatePass!123",
            "full_name": "Normal Candidate",
        },
    )
    cand_headers = {"Authorization": f"Bearer {cand_resp.json()['access_token']}"}
    assert client.get("/api/admin/legacy-sessions").status_code == 401
    assert client.get("/api/admin/legacy-sessions", headers=cand_headers).status_code == 403
    assert client.get("/api/admin/users", headers=cand_headers).status_code == 403
    assert client.get("/api/admin/audit-logs", headers=cand_headers).status_code == 403


def test_admin_claim_legacy_session_and_audit_trail_and_role_governance(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    from backend.app.services.admin_bootstrap import bootstrap_admin_user

    legacy_sid = f"sess_claim_{uuid.uuid4().hex[:10]}"
    admin_email = f"sa_{uuid.uuid4().hex[:6]}@pluto-admin.com"
    op_email = f"admin_{uuid.uuid4().hex[:6]}@pluto-admin.com"

    db = SessionLocal()
    try:
        bootstrap_admin_user(
            db,
            email=admin_email,
            password="SuperAdminPass!2026",
            full_name="Super Admin",
            role="super_admin",
        )
        bootstrap_admin_user(
            db,
            email=op_email,
            password="OperatorAdmin!2026",
            full_name="Regular Admin",
            role="admin",
        )
        db.add(
            InterviewSession(
                id=legacy_sid,
                job_id="job_sec_analyst",
                candidate_user_id=None,
                candidate_name="Sarthak Bhosale",
                interview_status="EVALUATED",
                interview_mode="self_practice",
            )
        )
        db.commit()
    finally:
        db.close()

    sa_login = client.post(
        "/api/auth/admin/login",
        json={"email": admin_email, "password": "SuperAdminPass!2026"},
    )
    assert sa_login.status_code == 200
    sa_headers = {"Authorization": f"Bearer {sa_login.json()['access_token']}"}

    op_login = client.post(
        "/api/auth/admin/login",
        json={"email": op_email, "password": "OperatorAdmin!2026"},
    )
    assert op_login.status_code == 200
    op_headers = {"Authorization": f"Bearer {op_login.json()['access_token']}"}

    # Register target candidate
    cand_reg = client.post(
        "/api/auth/register",
        json={
            "email": f"sarthak_verified_{uuid.uuid4().hex[:6]}@example.com",
            "password": "SarthakVerified!123",
            "full_name": "Sarthak Bhosale",
        },
    )
    assert cand_reg.status_code == 201
    target_user = cand_reg.json()["user"]
    cand_headers = {"Authorization": f"Bearer {cand_reg.json()['access_token']}"}

    # Unclaimed session visible in admin legacy queue
    unclaimed = client.get("/api/admin/legacy-sessions", headers=op_headers)
    assert unclaimed.status_code == 200
    assert any(row["session_id"] == legacy_sid for row in unclaimed.json()["sessions"])

    # Admin claims legacy session explicitly with reason
    claim_resp = client.post(
        f"/api/admin/sessions/{legacy_sid}/claim",
        headers=op_headers,
        json={"target_user_id": target_user["id"], "reason": "Verified candidate identity in person"},
    )
    assert claim_resp.status_code == 200, claim_resp.text
    assert claim_resp.json()["session"]["candidate_user_id"] == target_user["id"]

    # Re-claiming without force returns 409 conflict
    dup_claim = client.post(
        f"/api/admin/sessions/{legacy_sid}/claim",
        headers=op_headers,
        json={"target_user_id": target_user["id"], "reason": "Duplicate claim"},
    )
    assert dup_claim.status_code == 409

    # Candidate now owns the session in history and API
    cand_hist = client.get("/api/candidate/history", headers=cand_headers)
    assert any(row["session_id"] == legacy_sid for row in cand_hist.json()["sessions"])
    assert client.get(f"/api/interview/{legacy_sid}", headers=cand_headers).status_code == 200

    # Regular admin cannot change roles; only super_admin can
    role_denied = client.post(
        f"/api/admin/users/{target_user['id']}/role",
        headers=op_headers,
        json={"role": "admin", "reason": "Should fail"},
    )
    assert role_denied.status_code == 403

    role_ok = client.post(
        f"/api/admin/users/{target_user['id']}/role",
        headers=sa_headers,
        json={"role": "admin", "reason": "Promoted reviewer"},
    )
    assert role_ok.status_code == 200
    assert role_ok.json()["user"]["role"] == "admin"

    # Audit log contains both claim and role change
    logs = client.get("/api/admin/audit-logs", headers=sa_headers)
    assert logs.status_code == 200
    actions = [row["action"] for row in logs.json()["audit_logs"]]
    assert "admin.legacy_session_claimed" in actions
    assert "admin.user_role_updated" in actions

