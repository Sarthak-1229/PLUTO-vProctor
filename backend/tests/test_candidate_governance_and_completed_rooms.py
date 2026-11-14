"""Comprehensive integration test suite for Batch 3: Admin Candidate Governance & Completed Interviews Browser."""
from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import (
    AuditLog,
    CandidateProfile,
    InterviewReport,
    InterviewRoom,
    InterviewSession,
    Job,
    Resume,
    ResumeProfile,
    User,
)
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


def _create_user(role: str = "candidate", prefix: str = "user") -> tuple[dict, str]:
    db = SessionLocal()
    uid = f"usr_{uuid.uuid4().hex[:12]}"
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"
    pwd = "StrongPassword!123"
    try:
        user = User(
            id=uid,
            email=email,
            password_hash=hash_password(pwd),
            full_name=f"{prefix.title()} FullName",
            role=role,
            is_active=True,
            email_verified=True,
            token_version=0,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    with TestClient(app) as login_client:
        ep = "/api/auth/admin/login" if role in ("admin", "super_admin") else "/api/auth/login"
        resp = login_client.post(ep, json={"email": email, "password": pwd})
        assert resp.status_code == 200, resp.text
        return resp.json()["user"], resp.json()["access_token"]


def test_admin_candidate_list_search_and_filters(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "gov_admin")
    cand_charlie, _ = _create_user("candidate", "charlie_gov")
    cand_dana, _ = _create_user("candidate", "dana_gov")

    h_admin = {"Authorization": f"Bearer {admin_token}"}

    # 1. List users without filters
    res = client.get("/api/admin/users", headers=h_admin)
    assert res.status_code == 200
    data = res.json()
    assert "users" in data
    assert any(u["id"] == cand_charlie["id"] for u in data["users"])

    # 2. Search by name or email
    search_res = client.get("/api/admin/users?search=charlie_gov", headers=h_admin)
    assert search_res.status_code == 200
    s_users = search_res.json()["users"]
    assert len(s_users) >= 1
    assert any(u["id"] == cand_charlie["id"] for u in s_users)
    assert not any(u["id"] == cand_dana["id"] for u in s_users)

    # 3. Filter by role
    cand_filter = client.get("/api/admin/users?role=candidate", headers=h_admin)
    assert cand_filter.status_code == 200
    assert all(u["role"] == "candidate" for u in cand_filter.json()["users"])

    admin_filter = client.get("/api/admin/users?role=admin", headers=h_admin)
    assert admin_filter.status_code == 200
    assert all(u["role"] == "admin" for u in admin_filter.json()["users"])


def test_candidate_details_and_resumes_inspection(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "details_admin")
    cand_user, _ = _create_user("candidate", "profile_cand")

    # Seed profile and resume in DB
    db = SessionLocal()
    try:
        prof = CandidateProfile(
            id=f"prof_{uuid.uuid4().hex[:12]}",
            user_id=cand_user["id"],
            headline="Senior Backend Architect",
            experience_years=8.5,
            location="San Francisco, CA",
            technical_skills_json=["Python", "PostgreSQL", "FastAPI"],
            bio="Building high throughput distributed systems.",
            profile_completed=True,
        )
        db.add(prof)

        resume = Resume(
            id=f"res_{uuid.uuid4().hex[:12]}",
            user_id=cand_user["id"],
            original_filename="charlie_cv.pdf",
            storage_key=f"resumes/{uuid.uuid4().hex}.pdf",
            mime_type="application/pdf",
            file_size_bytes=102400,
            sha256_hash="dummy_hash_123",
            is_active=True,
        )
        db.add(resume)
        db.commit()
    finally:
        db.close()

    h_admin = {"Authorization": f"Bearer {admin_token}"}
    res = client.get(f"/api/admin/users/{cand_user['id']}", headers=h_admin)
    assert res.status_code == 200
    data = res.json()

    assert data["user"]["id"] == cand_user["id"]
    assert data["profile"]["headline"] == "Senior Backend Architect"
    assert "PostgreSQL" in data["profile"]["technical_skills"]
    assert len(data["resumes"]) == 1
    assert data["resumes"][0]["original_filename"] == "charlie_cv.pdf"
    assert "stats" in data


def test_candidate_interview_history_practice_and_hosted(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "hist_admin")
    cand_user, _ = _create_user("candidate", "hist_cand")

    # Seed one practice session and one hosted session with reports
    db = SessionLocal()
    try:
        job = db.query(Job).first()
        job_id = job.id if job else "swe_backend"

        sess_practice = InterviewSession(
            id=f"sess_{uuid.uuid4().hex[:12]}",
            job_id=job_id,
            candidate_user_id=cand_user["id"],
            candidate_name="Hist Cand",
            interview_mode="self_practice",
            interview_status="COMPLETED",
        )
        db.add(sess_practice)

        report_practice = InterviewReport(
            session_id=sess_practice.id,
            overall_score=85.0,
            grade="A",
            readiness_label="Ready",
            category_scores={"technical_accuracy": 85.0},
        )
        db.add(report_practice)

        sess_hosted = InterviewSession(
            id=f"sess_{uuid.uuid4().hex[:12]}",
            job_id=job_id,
            candidate_user_id=cand_user["id"],
            candidate_name="Hist Cand",
            interview_mode="hosted",
            interview_status="COMPLETED",
        )
        db.add(sess_hosted)
        db.commit()
    finally:
        db.close()

    h_admin = {"Authorization": f"Bearer {admin_token}"}
    res = client.get(f"/api/admin/users/{cand_user['id']}/history", headers=h_admin)
    assert res.status_code == 200
    data = res.json()

    sessions = data["sessions"]
    assert len(sessions) >= 2
    assert any(s["interview_mode"] == "self_practice" and s["has_report"] for s in sessions)
    assert any(s["interview_mode"] == "hosted" for s in sessions)


def test_interviews_browser_endpoint(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "browser_admin")
    h_admin = {"Authorization": f"Bearer {admin_token}"}

    res = client.get("/api/admin/interviews?limit=10", headers=h_admin)
    assert res.status_code == 200
    data = res.json()
    assert "interviews" in data
    assert "total" in data


def test_candidate_data_isolation_and_unauthorized_access(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    cand_user, cand_token = _create_user("candidate", "unauth_cand")
    h_cand = {"Authorization": f"Bearer {cand_token}"}

    # Candidate blocked from listing admin users (403)
    assert client.get("/api/admin/users", headers=h_cand).status_code == 403

    # Candidate blocked from viewing other user's admin details (403)
    assert client.get("/api/admin/users/usr_someother", headers=h_cand).status_code == 403

    # Candidate blocked from viewing other user's history (403)
    assert client.get("/api/admin/users/usr_someother/history", headers=h_cand).status_code == 403

    # Candidate blocked from browsing admin interviews (403)
    assert client.get("/api/admin/interviews", headers=h_cand).status_code == 403


def test_role_management_permissions_and_audit(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    super_admin, super_token = _create_user("super_admin", "sup_admin")
    admin_user, admin_token = _create_user("admin", "ord_admin")
    target_cand, _ = _create_user("candidate", "target_user")

    h_super = {"Authorization": f"Bearer {super_token}"}
    h_admin = {"Authorization": f"Bearer {admin_token}"}

    # 1. Ordinary admin cannot change user roles (403 Forbidden)
    r1 = client.post(
        f"/api/admin/users/{target_cand['id']}/role",
        headers=h_admin,
        json={"role": "admin", "reason": "Promote to recruiter"},
    )
    assert r1.status_code == 403

    # 2. Super admin successfully promotes candidate to admin
    r2 = client.post(
        f"/api/admin/users/{target_cand['id']}/role",
        headers=h_super,
        json={"role": "admin", "reason": "Promoted to engineering manager"},
    )
    assert r2.status_code == 200
    assert r2.json()["user"]["role"] == "admin"

    # 3. Verify audit event was logged
    db = SessionLocal()
    try:
        log = (
            db.query(AuditLog)
            .filter(AuditLog.action == "admin.user_role_updated", AuditLog.resource_id == target_cand["id"])
            .first()
        )
        assert log is not None
        assert log.actor_role == "super_admin"
        assert log.details_json["new_role"] == "admin"
    finally:
        db.close()


def test_last_active_admin_and_super_admin_protection(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    super_admin, super_token = _create_user("super_admin", "sole_super")
    h_super = {"Authorization": f"Bearer {super_token}"}

    # 1. Super admin cannot demote themselves (400 cannot_demote_self)
    r1 = client.post(
        f"/api/admin/users/{super_admin['id']}/role",
        headers=h_super,
        json={"role": "candidate", "reason": "Attempt self demotion"},
    )
    assert r1.status_code == 400
    assert "cannot_demote_self" in r1.text


def test_completed_room_serialization_and_report_access(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "room_report_admin")
    cand_user, _ = _create_user("candidate", "room_cand")
    h_admin = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create room
    create_room = client.post(
        "/api/admin/rooms",
        headers=h_admin,
        json={
            "title": "Completed Assessment With Report",
            "assigned_candidate_id": cand_user["id"],
            "duration_seconds": 1800,
            "proctoring_preset": "strict",
            "custom_questions": [{"question_text": "Explain Python GIL."}],
        },
    )
    assert create_room.status_code == 201
    room_id = create_room.json()["id"]

    # 2. Attach completed session and report
    db = SessionLocal()
    try:
        job = db.query(Job).first()
        sess = InterviewSession(
            id=f"sess_{uuid.uuid4().hex[:12]}",
            job_id=job.id if job else "swe_backend",
            candidate_user_id=cand_user["id"],
            interview_mode="hosted",
            interview_status="COMPLETED",
            room_id=room_id,
        )
        db.add(sess)

        rep = InterviewReport(
            session_id=sess.id,
            overall_score=92.5,
            grade="A",
            readiness_label="Strongly Qualified",
        )
        db.add(rep)

        room = db.query(InterviewRoom).filter(InterviewRoom.id == room_id).first()
        room.status = "COMPLETED"
        room.active_session_id = sess.id
        db.commit()
    finally:
        db.close()

    # 3. Retrieve room details
    room_get = client.get(f"/api/admin/rooms/{room_id}", headers=h_admin)
    assert room_get.status_code == 200
    r_data = room_get.json()

    assert r_data["status"] == "COMPLETED"
    assert r_data["active_session_id"] is not None
    assert r_data["report"]["overall_score"] == 92.5
    assert r_data["report"]["grade"] == "A"
    assert r_data["assigned_candidate"]["id"] == cand_user["id"]


def test_recording_access_authorization_and_idor(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    admin_user, admin_token = _create_user("admin", "video_admin")
    cand_alice, token_alice = _create_user("candidate", "alice_vid")
    cand_bob, token_bob = _create_user("candidate", "bob_vid")

    # Create dummy recording file in settings.STORAGE_DIR / "recordings"
    rec_dir = settings.STORAGE_DIR / "recordings"
    rec_dir.mkdir(parents=True, exist_ok=True)
    video_filename = f"rec_{uuid.uuid4().hex[:8]}.webm"
    video_file = rec_dir / video_filename
    video_file.write_bytes(b"\x1a\x45\xdf\xa3dummy_webm_bytes")

    db = SessionLocal()
    try:
        job = db.query(Job).first()
        sess = InterviewSession(
            id=f"sess_{uuid.uuid4().hex[:12]}",
            job_id=job.id if job else "swe_backend",
            candidate_user_id=cand_alice["id"],
            interview_mode="hosted",
            interview_status="COMPLETED",
            video_filename=video_filename,
        )
        db.add(sess)
        db.commit()
        session_id = sess.id
    finally:
        db.close()

    h_admin = {"Authorization": f"Bearer {admin_token}"}
    h_alice = {"Authorization": f"Bearer {token_alice}"}
    h_bob = {"Authorization": f"Bearer {token_bob}"}

    # 1. Admin can access recording (200 OK)
    r_admin = client.get(f"/api/interview/{session_id}/video", headers=h_admin)
    assert r_admin.status_code == 200
    assert r_admin.headers["content-type"] == "video/webm"

    # 2. Alice (owner) can access recording (200 OK)
    r_alice = client.get(f"/api/interview/{session_id}/video", headers=h_alice)
    assert r_alice.status_code == 200

    # 3. Bob (unauthorized candidate) receives 403 Forbidden
    r_bob = client.get(f"/api/interview/{session_id}/video", headers=h_bob)
    assert r_bob.status_code == 403
    assert "forbidden_session_access" in r_bob.text
