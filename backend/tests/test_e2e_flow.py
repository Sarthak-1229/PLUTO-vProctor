"""End-to-end integration tests for PLUTO vProctor.

Validates Section 10 Definition of Done:
resume upload -> screening -> question generation -> recording upload ->
video retrieval -> report generation -> PDF download -> privacy data deletion.
"""
from __future__ import annotations

import io
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.db.database import get_db, SessionLocal
from backend.app.db.models import Job
from backend.app.main import app

client = TestClient(app)
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_full_mock_interview_e2e_flow():
    # 1. Fetch available jobs
    jobs_res = client.get("/api/jobs")
    assert jobs_res.status_code == 200
    jobs = jobs_res.json()
    assert len(jobs) >= 12
    job = jobs[0]
    job_id = job["id"]

    # 2. Upload resume for screening
    resume_path = FIXTURES_DIR / "resume_senior_sec_analyst.pdf"
    assert resume_path.exists()

    with open(resume_path, "rb") as f:
        upload_res = client.post(
            "/api/resume/upload",
            data={"job_id": job_id},
            files={"file": ("resume.pdf", f, "application/pdf")},
        )
    assert upload_res.status_code == 200
    screening_data = upload_res.json()
    assert "session_id" in screening_data
    session_id = screening_data["session_id"]
    assert screening_data["fit_score"] > 0.0

    # 3. Start interview session and verify question list
    start_res = client.post(f"/api/interview/{session_id}/start")
    assert start_res.status_code == 200
    session_data = start_res.json()
    assert "questions" in session_data
    assert len(session_data["questions"]) >= 4

    # 4. Upload mock interview recording (.webm)
    dummy_video_bytes = b"\x1a\x45\xdf\xa3" + b"\x00" * 2048  # minimal EBML header
    rec_res = client.post(
        f"/api/interview/{session_id}/recording",
        files={"file": (f"{session_id}_interview.webm", dummy_video_bytes, "video/webm")},
    )
    assert rec_res.status_code == 200
    assert rec_res.json()["status"] == "success"

    # 5. Verify video streaming endpoint
    video_res = client.get(f"/api/interview/{session_id}/video")
    assert video_res.status_code == 200
    assert len(video_res.content) == len(dummy_video_bytes)

    # 6. Verify Settings endpoints
    settings_res = client.get("/api/settings")
    assert settings_res.status_code == 200
    assert "gaze_tolerance_x" in settings_res.json()

    put_res = client.put(
        "/api/settings",
        json={"speech_pause_sec": 4.0, "filler_penalty": 0.8},
    )
    assert put_res.status_code == 200
    assert put_res.json()["settings"]["speech_pause_sec"] == 4.0

    # 7. Generate structured report & PDF
    report_res = client.get(f"/api/report/{session_id}")
    assert report_res.status_code == 200
    rep_json = report_res.json()
    assert "overall_score" in rep_json
    assert "category_scores" in rep_json
    assert "deduction_timeline" in rep_json

    pdf_res = client.get(f"/api/report/{session_id}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF")

    # 8. Privacy compliance: Delete session and recording
    del_res = client.delete(f"/api/interview/{session_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # Verify session is gone
    check_res = client.get(f"/api/interview/{session_id}")
    assert check_res.status_code == 404
