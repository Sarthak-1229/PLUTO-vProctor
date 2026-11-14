"""Tests for report routing, authorization, IDOR isolation, and deep-linking access."""
from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import Company, InterviewReport, InterviewSession, Job, User
from backend.app.main import app
from backend.app.services.security_service import create_access_token, hash_password

client = TestClient(app)


def _get_or_create_user(email: str, role: str, name: str) -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                password_hash=hash_password("ReportPass123!"),
                full_name=name,
                role=role,
                is_active=True,
                email_verified=True,
                token_version=1,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
    finally:
        db.close()


def _setup_session_with_report(candidate_user_id: str) -> str:
    db = SessionLocal()
    try:
        comp = db.query(Company).first()
        if not comp:
            comp = Company(id="comp_test", name="Test Corp", industry="Tech")
            db.add(comp)
            db.commit()

        job = db.query(Job).first()
        if not job:
            job = Job(id="job_test", title="Software Engineer", company="Test Corp", company_id=comp.id)
            db.add(job)
            db.commit()

        sid = f"sess_rpt_{uuid.uuid4().hex[:8]}"
        session = InterviewSession(
            id=sid,
            job_id=job.id,
            candidate_user_id=candidate_user_id,
            candidate_name="Test Candidate",
            interview_mode="self_practice",
            interview_status="ANALYZED",
        )
        db.add(session)
        db.commit()

        report = InterviewReport(
            session_id=sid,
            overall_score=88.5,
            grade="A",
            readiness_label="Ready for Deployment",
            category_scores={
                "Technical Knowledge": 90,
                "Communication & Fluency": 85,
                "Focus & Proctoring": 92,
                "Resume & Experience Fit": 87,
            },
            summary={
                "candidate_name": "Test Candidate",
                "job_title": "Software Engineer",
                "company": "Test Corp",
                "radar_metrics": {
                    "Technical Depth": 90,
                    "Problem Solving": 88,
                    "Communication": 85,
                    "Code Quality": 89,
                    "Delivery & Composure": 92,
                },
            },
        )
        db.add(report)
        db.commit()
        return sid
    finally:
        db.close()


def test_report_access_authorization_and_idor_protection(monkeypatch):
    """Verify report access matrix: Candidate A (own), Candidate B (forbidden), Admin (allowed), Unauth (401)."""
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)

    cand_a = _get_or_create_user("cand_a_report@pluto.local", "candidate", "Alice")
    cand_b = _get_or_create_user("cand_b_report@pluto.local", "candidate", "Bob")
    admin = _get_or_create_user("admin_report@pluto.local", "admin", "Admin Evaluator")

    tok_a, _ = create_access_token(user_id=cand_a.id, role=cand_a.role, token_version=cand_a.token_version)
    tok_b, _ = create_access_token(user_id=cand_b.id, role=cand_b.role, token_version=cand_b.token_version)
    tok_admin, _ = create_access_token(user_id=admin.id, role=admin.role, token_version=admin.token_version)

    headers_a = {"Authorization": f"Bearer {tok_a}"}
    headers_b = {"Authorization": f"Bearer {tok_b}"}
    headers_admin = {"Authorization": f"Bearer {tok_admin}"}

    # Session belonging to Candidate A
    session_id_a = _setup_session_with_report(candidate_user_id=cand_a.id)

    # 1. Candidate A accesses their own report -> 200 OK
    res_a = client.get(f"/api/report/{session_id_a}", headers=headers_a)
    assert res_a.status_code == 200
    report_data = res_a.json()
    assert report_data["session_id"] == session_id_a
    assert isinstance(report_data["overall_score"], (int, float))
    assert "radar_metrics" in report_data

    # 2. Candidate B attempts to access Candidate A's report -> 403 Forbidden
    res_b = client.get(f"/api/report/{session_id_a}", headers=headers_b)
    assert res_b.status_code == 403
    assert res_b.json()["error"]["code"] == "forbidden_session_access"

    # 3. Admin accesses Candidate A's report -> 200 OK
    res_admin = client.get(f"/api/report/{session_id_a}", headers=headers_admin)
    assert res_admin.status_code == 200
    assert res_admin.json()["session_id"] == session_id_a

    # 4. Unauthenticated user attempts access when AUTH_ENABLED=True -> 401 Unauthorized
    res_unauth = client.get(f"/api/report/{session_id_a}")
    assert res_unauth.status_code == 401
    assert res_unauth.json()["error"]["code"] == "authentication_required"

    # 5. Non-existent session ID -> 404 Not Found
    res_404 = client.get("/api/report/sess_nonexistent_9999", headers=headers_a)
    assert res_404.status_code == 404

    # 6. PDF Report authorization
    # Candidate A gets own PDF -> 200 OK
    res_pdf_a = client.get(f"/api/report/{session_id_a}/pdf", headers=headers_a)
    assert res_pdf_a.status_code == 200
    assert res_pdf_a.headers["content-type"] == "application/pdf"

    # Candidate B blocked from Candidate A's PDF -> 403 Forbidden
    res_pdf_b = client.get(f"/api/report/{session_id_a}/pdf", headers=headers_b)
    assert res_pdf_b.status_code == 403

    # Admin gets PDF -> 200 OK
    res_pdf_admin = client.get(f"/api/report/{session_id_a}/pdf", headers=headers_admin)
    assert res_pdf_admin.status_code == 200
    assert res_pdf_admin.headers["content-type"] == "application/pdf"
