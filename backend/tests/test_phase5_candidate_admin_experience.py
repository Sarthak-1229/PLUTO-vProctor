"""Comprehensive automated test suite for Phase 5: Candidate and Admin Experience."""
from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import AuditLog, InterviewReport, InterviewRoom, InterviewSession, Job, ProctoringEvent, User
from backend.app.main import app
from backend.app.services.security_service import hash_password, reset_rate_limits


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


def _create_user(role: str = "candidate", prefix: str = "cand5") -> tuple[dict, str]:
    db = SessionLocal()
    uid = f"usr_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "StrongPassword!123"
    try:
        user = User(
            id=uid,
            email=email,
            password_hash=hash_password(pwd),
            full_name=f"{prefix.title()} Candidate",
            role=role,
            is_active=True,
            email_verified=True,
            token_version=0,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    # Login to obtain JWT
    login_ep = "/api/auth/admin/login" if role in ("admin", "super_admin") else "/api/auth/login"
    with TestClient(app) as tc:
        resp = tc.post(login_ep, json={"email": email, "password": pwd})
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]
        return {"id": uid, "email": email, "role": role}, token


def test_candidate_analytics_and_roadmap_computation(client, monkeypatch):
    """Verify candidate analytics trend and personalized roadmap milestone synthesis."""
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    cand_user, cand_token = _create_user("candidate", "cand_analytics")
    headers = {"Authorization": f"Bearer {cand_token}"}

    # 1. New candidate with 0 interviews returns clean empty state
    res_empty = client.get("/api/candidate/analytics", headers=headers)
    assert res_empty.status_code == 200
    empty_data = res_empty.json()
    assert empty_data["total_interviews"] == 0
    assert empty_data["average_score"] == 0.0

    # 2. Seed 2 completed sessions with reports
    db = SessionLocal()
    try:
        jid = f"job_p5_{uuid.uuid4().hex[:8]}"
        job = Job(
            id=jid,
            title="Systems Architect",
            company="KernelCorp",
            question_domains=["Systems"],
            required_skills=["Linux", "C++", "Concurrency"],
            min_experience_years=5,
            pass_threshold=0.70,
        )
        db.add(job)

        s1_id = f"sess_p5_1_{uuid.uuid4().hex[:8]}"
        s2_id = f"sess_p5_2_{uuid.uuid4().hex[:8]}"

        sess1 = InterviewSession(
            id=s1_id,
            job_id=jid,
            candidate_user_id=cand_user["id"],
            candidate_name="Analytics Candidate",
            interview_mode="self_practice",
            interview_status="ANALYZED",
        )
        rep1 = InterviewReport(
            session_id=s1_id,
            overall_score=72.0,
            grade="B",
            readiness_label="Ready with Minor Polish",
            category_scores={"technical_depth": 70.0, "communication": 75.0, "proctoring_integrity": 80.0, "resume_fit": 65.0},
        )

        sess2 = InterviewSession(
            id=s2_id,
            job_id=jid,
            candidate_user_id=cand_user["id"],
            candidate_name="Analytics Candidate",
            interview_mode="hosted",
            interview_status="ANALYZED",
        )
        rep2 = InterviewReport(
            session_id=s2_id,
            overall_score=86.0,
            grade="A",
            readiness_label="Interview Ready",
            category_scores={"technical_depth": 88.0, "communication": 82.0, "proctoring_integrity": 90.0, "resume_fit": 84.0},
        )

        db.add_all([sess1, rep1, sess2, rep2])
        db.commit()
    finally:
        db.close()

    # 3. Analytics response now aggregates historical metrics
    res_analytics = client.get("/api/candidate/analytics", headers=headers)
    assert res_analytics.status_code == 200
    adata = res_analytics.json()
    assert adata["total_interviews"] == 2
    assert adata["completed_interviews"] == 2
    assert adata["average_score"] == 79.0
    assert len(adata["score_trend"]) == 2
    assert adata["score_trend"][0]["score"] == 72.0
    assert adata["score_trend"][1]["score"] == 86.0
    assert adata["score_trend"][1]["mode"] == "hosted"

    # 4. Roadmap response compiles personalized milestones and drills
    res_roadmap = client.get("/api/candidate/roadmap", headers=headers)
    assert res_roadmap.status_code == 200
    rdata = res_roadmap.json()
    assert "milestones" in rdata
    assert len(rdata["milestones"]) == 4
    assert "primary_focus_area" in rdata
    assert "recommended_drills" in rdata
    assert len(rdata["recommended_drills"]) >= 1


def test_candidate_analytics_idor_isolation(client, monkeypatch):
    """Verify Candidate A cannot access or leak Candidate B's analytics or roadmap."""
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    alice, token_alice = _create_user("candidate", "alice_p5")
    bob, token_bob = _create_user("candidate", "bob_p5")

    h_alice = {"Authorization": f"Bearer {token_alice}"}
    h_bob = {"Authorization": f"Bearer {token_bob}"}

    # Alice fetches own analytics -> 200 OK
    res_a = client.get("/api/candidate/analytics", headers=h_alice)
    assert res_a.status_code == 200

    # Unauthenticated request rejected -> 401
    res_unauth = client.get("/api/candidate/analytics")
    assert res_unauth.status_code == 401


def test_admin_analytics_overview_and_activity(client, monkeypatch):
    """Verify administrator platform overview KPIs and activity monitoring."""
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "admin_analytics")
    cand_user, cand_token = _create_user("candidate", "cand_nonadmin")

    h_admin = {"Authorization": f"Bearer {admin_token}"}
    h_cand = {"Authorization": f"Bearer {cand_token}"}

    # Candidate access to admin analytics is forbidden -> 403
    cand_resp = client.get("/api/admin/analytics/overview", headers=h_cand)
    assert cand_resp.status_code == 403

    # Admin access succeeds -> 200
    admin_resp = client.get("/api/admin/analytics/overview", headers=h_admin)
    assert admin_resp.status_code == 200
    overview = admin_resp.json()
    assert "users" in overview
    assert overview["users"]["total_candidates"] >= 1
    assert "interviews" in overview
    assert "rooms" in overview
    assert "proctoring" in overview

    # Admin activity feed
    act_resp = client.get("/api/admin/analytics/activity?limit=10", headers=h_admin)
    assert act_resp.status_code == 200
    activity = act_resp.json()
    assert "activity" in activity
    assert isinstance(activity["activity"], list)

