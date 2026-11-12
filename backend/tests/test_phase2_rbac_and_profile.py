"""TDD tests for Phase 2 server-side RBAC, cross-candidate IDOR isolation, and candidate profiles."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import InterviewReport, InterviewSession, User
from backend.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_limits():
    from backend.app.services.security_service import reset_rate_limits

    reset_rate_limits()
    yield
    reset_rate_limits()


def _register_and_token(client, prefix: str = "cand") -> tuple[dict, str]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPassword!123", "full_name": f"{prefix.title()} User"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["user"], data["access_token"]


def _create_admin_and_token(client) -> tuple[dict, str]:
    from backend.app.services.security_service import hash_password

    email = f"admin_{uuid.uuid4().hex[:8]}@pluto-admin.com"
    db = SessionLocal()
    try:
        admin = User(
            id=f"usr_{uuid.uuid4().hex[:16]}",
            email=email,
            password_hash=hash_password("AdminSecretPass!2026"),
            full_name="Phase2 Admin",
            role="admin",
            is_active=True,
            email_verified=True,
        )
        db.add(admin)
        db.commit()
    finally:
        db.close()

    resp = client.post(
        "/api/auth/admin/login",
        json={"email": email, "password": "AdminSecretPass!2026"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["user"], resp.json()["access_token"]


def test_auth_enabled_enforces_401_on_protected_routes_and_keeps_catalog_public(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)

    assert client.get("/api/jobs").status_code == 200
    assert client.get("/api/candidate/profile").status_code == 401
    assert client.put("/api/candidate/profile", json={"headline": "Engineer"}).status_code == 401
    assert client.get("/api/candidate/history").status_code == 401
    assert client.get("/api/settings").status_code == 401
    assert client.put("/api/settings", json={"preset": "normal"}).status_code == 401

    assert (
        client.post(
            "/api/resume/upload",
            data={"job_id": "job_sec_analyst", "candidate_name": "Anon"},
            files={"file": ("resume.txt", b"Python security skills", "text/plain")},
        ).status_code
        == 401
    )
    assert client.get("/api/interview/sess_nonexistent").status_code == 401
    assert client.post("/api/analysis/sess_nonexistent/run").status_code == 401
    assert client.get("/api/report/sess_nonexistent").status_code == 401


def test_cross_candidate_idor_blocked_and_admin_rbac_enforced(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    cand_a, token_a = _register_and_token(client, "alice")
    cand_b, token_b = _register_and_token(client, "bob")
    _, token_admin = _create_admin_and_token(client)

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # Candidate A uploads resume for job interview session
    up = client.post(
        "/api/resume/upload",
        headers=headers_a,
        data={"job_id": "job_sec_analyst", "candidate_name": cand_a["full_name"]},
        files={"file": ("alice.txt", b"Network Security & Cryptography Application Security 3 years", "text/plain")},
    )
    assert up.status_code == 200, up.text
    sid_a = up.json()["session_id"]

    # Confirm DB ownership recorded
    db = SessionLocal()
    try:
        sess = db.query(InterviewSession).filter(InterviewSession.id == sid_a).first()
        assert sess is not None
        assert sess.candidate_user_id == cand_a["id"]
        db.add(
            InterviewReport(
                session_id=sid_a,
                overall_score=84.5,
                grade="B",
                readiness_label="Ready",
                category_scores={"technical_depth": 85.0},
                summary={"executive_summary": "Solid", "strengths": ["Crypto"], "concrete_tips": ["Explain more"]},
            )
        )
        db.commit()
    finally:
        db.close()

    # Candidate B must get 403 across EVERY session/analysis/report/delete endpoint for Candidate A's session
    assert client.get(f"/api/interview/{sid_a}", headers=headers_b).status_code == 403
    assert client.post(f"/api/interview/{sid_a}/start", headers=headers_b).status_code == 403
    assert client.get(f"/api/interview/{sid_a}/video", headers=headers_b).status_code == 403
    assert client.post(f"/api/analysis/{sid_a}/run", headers=headers_b).status_code == 403
    assert client.get(f"/api/analysis/{sid_a}/status", headers=headers_b).status_code == 403
    assert client.get(f"/api/report/{sid_a}", headers=headers_b).status_code == 403
    assert client.get(f"/api/report/{sid_a}/pdf", headers=headers_b).status_code == 403
    assert client.delete(f"/api/interview/{sid_a}", headers=headers_b).status_code == 403

    # Candidate A owns the session and can view status & report
    assert client.get(f"/api/interview/{sid_a}", headers=headers_a).status_code == 200
    assert client.get(f"/api/report/{sid_a}", headers=headers_a).status_code == 200

    # Admin can access settings and manage global sensitivity; candidates get 403
    assert client.get("/api/settings", headers=headers_a).status_code == 403
    assert client.put("/api/settings", headers=headers_a, json={"preset": "strict"}).status_code == 403
    assert client.get("/api/settings", headers=headers_admin).status_code == 200
    assert client.get(f"/api/report/{sid_a}", headers=headers_admin).status_code == 200


def test_candidate_profile_persistence_blocks_role_escalation_and_isolates_history(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    cand_a, token_a = _register_and_token(client, "charlie")
    _, token_b = _register_and_token(client, "dana")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Update profile
    upd = client.put(
        "/api/candidate/profile",
        headers=headers_a,
        json={
            "full_name": "Charlie Updated",
            "headline": "Backend & Security Engineer",
            "location": "Pune, India",
            "education_level": "Bachelor",
            "education_details": [{"institution": "VIT", "degree": "B.Tech", "field": "Computer Science", "year": 2025}],
            "experience_years": 1.5,
            "experience_summary": [{"title": "Software Intern", "company": "Acme", "duration": "6 months"}],
            "technical_skills": ["Python", "SQL", "Docker"],
            "preferred_roles": ["Backend Developer"],
            "portfolio_links": {"github": "https://github.com/charlie-dev"},
            "bio": "Building reliable APIs.",
        },
    )
    assert upd.status_code == 200, upd.text
    prof = upd.json()["profile"]
    assert prof["headline"] == "Backend & Security Engineer"
    assert prof["technical_skills"] == ["Python", "SQL", "Docker"]
    assert prof["profile_completed"] is True

    # Mass-assignment of role in profile update must fail validation
    bad_upd = client.put(
        "/api/candidate/profile",
        headers=headers_a,
        json={"headline": "Hacked", "role": "admin"},
    )
    assert bad_upd.status_code == 422

    # Create a session for Charlie and check /api/candidate/history isolates properly
    up_a = client.post(
        "/api/resume/upload",
        headers=headers_a,
        data={"job_id": "job_sec_analyst", "candidate_name": "Charlie Updated"},
        files={"file": ("charlie.txt", b"Python security skills", "text/plain")},
    )
    assert up_a.status_code == 200
    sid_a = up_a.json()["session_id"]

    hist_a = client.get("/api/candidate/history", headers=headers_a)
    assert hist_a.status_code == 200
    sids_a = [item["session_id"] for item in hist_a.json()["sessions"]]
    assert sid_a in sids_a

    # Dana's history must NOT contain Charlie's session (nor unclaimed legacy sessions)
    hist_b = client.get("/api/candidate/history", headers=headers_b)
    assert hist_b.status_code == 200
    assert hist_b.json()["sessions"] == []


def test_offline_self_practice_backward_compatible_when_auth_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    up = client.post(
        "/api/resume/upload",
        data={"job_id": "job_sec_analyst", "candidate_name": "Offline Practice"},
        files={"file": ("offline.txt", b"Network Security Python", "text/plain")},
    )
    assert up.status_code == 200
    sid = up.json()["session_id"]
    # Unclaimed session is accessible anonymously in offline practice mode
    assert client.get(f"/api/interview/{sid}").status_code == 200


def test_offline_mode_blocks_anonymous_and_cross_user_access_to_claimed_sessions(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", False)
    cand_a, token_a = _register_and_token(client, "eve_owner")
    cand_b, token_b = _register_and_token(client, "mallory_attacker")
    _, token_admin = _create_admin_and_token(client)

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # Create a session owned by Candidate A
    up = client.post(
        "/api/resume/upload",
        headers=headers_a,
        data={"job_id": "job_sec_analyst", "candidate_name": cand_a["full_name"]},
        files={"file": ("eve.txt", b"Python cybersecurity cloud aws", "text/plain")},
    )
    assert up.status_code == 200
    sid = up.json()["session_id"]

    # In offline mode (AUTH_ENABLED=False), an anonymous request to Eve's private session must return 401
    anon_resp = client.get(f"/api/interview/{sid}")
    assert anon_resp.status_code == 401

    # Another candidate (Mallory) must return 403
    other_resp = client.get(f"/api/interview/{sid}", headers=headers_b)
    assert other_resp.status_code == 403

    # Owner (Eve) must succeed
    owner_resp = client.get(f"/api/interview/{sid}", headers=headers_a)
    assert owner_resp.status_code == 200

    # Admin must succeed
    admin_resp = client.get(f"/api/interview/{sid}", headers=headers_admin)
    assert admin_resp.status_code == 200
