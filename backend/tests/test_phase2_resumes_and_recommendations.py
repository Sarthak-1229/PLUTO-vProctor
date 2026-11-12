"""TDD tests for Phase 2 multi-resume storage, editable parsed profiles, and universal job recommendations."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import JobRecommendation, Resume, ResumeProfile
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


def _register_cand(client, prefix: str = "resuser") -> tuple[dict, str]:
    resp = client.post(
        "/api/auth/register",
        json={
            "email": f"{prefix}_{uuid.uuid4().hex[:8]}@example.com",
            "password": "ResumeUserPass!123",
            "full_name": f"{prefix.title()} Dev",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["user"], resp.json()["access_token"]


def test_spoofed_magic_bytes_and_oversized_resume_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    _, token = _register_cand(client, "spoof")
    headers = {"Authorization": f"Bearer {token}"}

    # PE executable spoofed as .pdf
    spoof = client.post(
        "/api/resumes/upload",
        headers=headers,
        files={"file": ("evil.pdf", b"MZ\x90\x00This is an executable", "application/pdf")},
    )
    assert spoof.status_code == 400

    # Oversized > 5 MB rejected with 413
    too_big = b"A" * (5 * 1024 * 1024 + 64)
    oversized = client.post(
        "/api/resumes/upload",
        headers=headers,
        files={"file": ("huge.txt", too_big, "text/plain")},
    )
    assert oversized.status_code == 413

    # Unsupported extension rejected
    bad_ext = client.post(
        "/api/resumes/upload",
        headers=headers,
        files={"file": ("script.sh", b"#!/bin/sh\necho hi", "text/plain")},
    )
    assert bad_ext.status_code == 400


def test_resume_upload_review_edit_confirm_cross_user_isolation_and_delete(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    user_a, token_a = _register_cand(client, "owner")
    _, token_b = _register_cand(client, "other")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    resume_text = (
        b"Owner Dev\n"
        b"Skills: Python, SQL, Docker, FastAPI\n"
        b"Experience\n"
        b"Jan 2022 - Jan 2024 Software Engineer\n"
        b"Education\n"
        b"Bachelor of Technology in Computer Science\n"
    )
    up = client.post(
        "/api/resumes/upload",
        headers=headers_a,
        files={"file": ("../../etc/passwd_resume.txt", resume_text, "text/plain")},
    )
    assert up.status_code == 201, up.text
    payload = up.json()
    resume_id = payload["resume"]["id"]
    assert payload["resume"]["storage_key"].startswith("res_")
    assert ".." not in payload["resume"]["storage_key"]
    assert payload["resume"]["original_filename"] == "passwd_resume.txt"
    assert "Python" in payload["resume_profile"]["extracted_data"]["skills"]
    assert payload["resume_profile"]["confirmed_by_user"] is False

    # Private disk file exists in STORAGE_DIR/resumes under random key
    saved_disk = settings.STORAGE_DIR / "resumes" / payload["resume"]["storage_key"]
    assert saved_disk.exists()

    # Candidate B cannot view, edit, confirm, or delete Candidate A's resume
    assert client.get(f"/api/resumes/{resume_id}", headers=headers_b).status_code == 403
    assert client.put(f"/api/resumes/{resume_id}/profile", headers=headers_b, json={"skills": ["Hack"]}).status_code == 403
    assert client.post(f"/api/resumes/{resume_id}/confirm", headers=headers_b).status_code == 403
    assert client.delete(f"/api/resumes/{resume_id}", headers=headers_b).status_code == 403

    # Candidate A edits parsed resume fields and confirms accuracy
    edit = client.put(
        f"/api/resumes/{resume_id}/profile",
        headers=headers_a,
        json={
            "candidate_name": "Owner Verified",
            "skills": ["Python", "Docker", "Kubernetes", "PostgreSQL"],
            "experience_years": 2.5,
            "education": {"degree": "Master", "fields": ["Computer Science"]},
        },
    )
    assert edit.status_code == 200
    assert "Kubernetes" in edit.json()["resume_profile"]["effective_data"]["skills"]
    assert edit.json()["resume_profile"]["provenance"]["skills"]["source"] == "manual_edit"

    conf = client.post(f"/api/resumes/{resume_id}/confirm", headers=headers_a)
    assert conf.status_code == 200
    assert conf.json()["resume_profile"]["confirmed_by_user"] is True

    # Delete removes both DB rows AND private file cleanly
    deleted = client.delete(f"/api/resumes/{resume_id}", headers=headers_a)
    assert deleted.status_code == 200
    assert not saved_disk.exists()

    db = SessionLocal()
    try:
        assert db.query(Resume).filter(Resume.id == resume_id).first() is None
        assert db.query(ResumeProfile).filter(ResumeProfile.resume_id == resume_id).first() is None
    finally:
        db.close()


def test_universal_recommendations_work_without_interview_for_resume_only_profile_only_and_combined(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)

    # 1. Resume-only candidate (0 interviews, no manual profile edited)
    u_res, tok_res = _register_cand(client, "resonly")
    h_res = {"Authorization": f"Bearer {tok_res}"}
    client.post(
        "/api/resumes/upload",
        headers=h_res,
        files={"file": ("cloud.txt", b"Skills: AWS, Docker, Kubernetes, CI/CD\nBachelor in Computer Science", "text/plain")},
    )
    rec_res = client.get("/api/jobs/recommendations", headers=h_res)
    assert rec_res.status_code == 200, rec_res.text
    d_res = rec_res.json()
    assert d_res["source_type"] == "resume"
    assert d_res["has_completed_interview"] is False
    assert len(d_res["recommendations"]) >= 3
    top_res = d_res["recommendations"][0]
    assert top_res["match_score"] > 0
    assert len(top_res["matched_skills"]) >= 1
    assert "why_recommended" in top_res and top_res["why_recommended"]

    # 2. Manual-profile-only candidate (0 interviews, 0 resumes uploaded)
    u_prof, tok_prof = _register_cand(client, "profonly")
    h_prof = {"Authorization": f"Bearer {tok_prof}"}
    client.put(
        "/api/candidate/profile",
        headers=h_prof,
        json={
            "headline": "Aspiring Security Analyst",
            "education_level": "Bachelor",
            "experience_years": 1.0,
            "technical_skills": ["Network Security & Cryptography", "Application Security", "Python"],
            "preferred_roles": ["Security Analyst"],
        },
    )
    rec_prof = client.get("/api/jobs/recommendations", headers=h_prof)
    assert rec_prof.status_code == 200, rec_prof.text
    d_prof = rec_prof.json()
    assert d_prof["source_type"] == "profile"
    assert len(d_prof["recommendations"]) >= 3
    assert any("Security" in r["title"] for r in d_prof["recommendations"][:3])

    # 3. Combined (manual profile + edited resume) merges both signals transparently
    client.post(
        "/api/resumes/upload",
        headers=h_prof,
        files={"file": ("sec.txt", b"Skills: Docker, Linux\nBachelor", "text/plain")},
    )
    rec_comb = client.get("/api/jobs/recommendations", headers=h_prof)
    assert rec_comb.status_code == 200
    assert rec_comb.json()["source_type"] == "combined"

    # Recommendations persisted per candidate in DB
    db = SessionLocal()
    try:
        rows = db.query(JobRecommendation).filter(JobRecommendation.user_id == u_prof["id"]).all()
        assert len(rows) >= 3
    finally:
        db.close()

    # Unauthenticated recommendations rejected when AUTH_ENABLED=True
    assert client.get("/api/jobs/recommendations").status_code == 401

