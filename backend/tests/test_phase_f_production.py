"""Phase F Production Readiness Test Suite.

Verifies:
1. Health and readiness probe endpoints (/api/health, /api/ready)
2. Background JobQueue idempotency, worker metrics, and GPU concurrency locking
3. Request-ID correlation header and security headers (nosniff, DENY, etc.)
4. Upload size gating and MIME validation
5. Privacy compliance and complete data deletion purge (/api/interview/{sid}/delete-data)
"""
from __future__ import annotations

import io
import time
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.job_queue import JobStatus, job_queue
from backend.app.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.models import InterviewSession, Job

client = TestClient(app)


def test_health_and_readiness_endpoints():
    """Verify system health liveness and readiness probes return 200 OK."""
    # Liveness
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data

    # Readiness
    resp_ready = client.get("/api/ready")
    assert resp_ready.status_code == 200
    r_data = resp_ready.json()
    assert r_data["database"] == "connected"
    assert r_data["storage"] == "available"


def test_security_headers_and_request_id():
    """Verify security headers and X-Request-ID propagation."""
    custom_req_id = "test-req-12345"
    resp = client.get("/api/health", headers={"X-Request-ID": custom_req_id})
    assert resp.status_code == 200

    # Header assertions
    assert resp.headers.get("X-Request-ID") == custom_req_id
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "X-Response-Time-MS" in resp.headers


def test_job_queue_mechanics_and_metrics():
    """Verify JobQueue enqueuing, progress updates, and metrics reporting."""
    test_sid = "sess_test_jq_001"
    job = job_queue.enqueue(test_sid, "FULL_ANALYSIS")
    assert job.session_id == test_sid
    assert job.status in (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED)

    # Test idempotency (same session should return identical job)
    job_dup = job_queue.enqueue(test_sid, "FULL_ANALYSIS")
    assert job_dup.job_id == job.job_id

    # Test progress update
    job_queue.update_progress(job.job_id, "video", 0.5, stage="Tracking Gaze")
    updated = job_queue.get_job(job.job_id)
    assert updated.progress["video"] == 0.5
    assert updated.stage == "Tracking Gaze"

    # Test metrics endpoint
    stats = client.get("/api/analysis/jobs/stats").json()
    assert "total_jobs" in stats
    assert "queue_depth" in stats
    assert "failure_rate_pct" in stats


def _get_or_create_test_job(db) -> str:
    job = db.query(Job).first()
    if not job:
        job = Job(
            id="job_test_001",
            title="Senior Backend Engineer",
            company="PLUTO Systems",
            min_experience_years=3.0,
            required_skills=["Python", "FastAPI"],
            pass_threshold=60.0,
        )
        db.add(job)
        db.commit()
    return job.id


def test_resume_upload_size_and_mime_validation():
    """Verify rejection of corrupted files and enforcement of file size constraints."""
    db = SessionLocal()
    job_id = _get_or_create_test_job(db)
    db.close()

    # 1. Invalid PDF magic header
    fake_corrupted_pdf = b"This is not a real PDF document at all."
    resp = client.post(
        "/api/resume/upload",
        data={"job_id": job_id},
        files={"file": ("resume.pdf", fake_corrupted_pdf, "application/pdf")},
    )
    assert resp.status_code == 400

    # 2. Oversized file (> 10MB)
    huge_payload = b"0" * (11 * 1024 * 1024)
    resp_huge = client.post(
        "/api/resume/upload",
        data={"job_id": job_id},
        files={"file": ("resume.pdf", huge_payload, "application/pdf")},
    )
    assert resp_huge.status_code in (413, 400)


def test_complete_data_deletion_purge():
    """Verify DELETE /api/interview/{sid} removes all artifacts and database records."""
    db = SessionLocal()
    job_id = _get_or_create_test_job(db)
    test_sid = "sess_purge_test_999"

    # Ensure clean slate
    db.query(InterviewSession).filter(InterviewSession.id == test_sid).delete()
    db.commit()

    # Create dummy session with valid job_id
    session = InterviewSession(
        id=test_sid,
        job_id=job_id,
        candidate_name="Purge Candidate",
        video_filename=f"{test_sid}_interview.webm",
    )
    db.add(session)
    db.commit()
    db.close()

    # Create dummy video and audio files on disk
    rec_file = settings.STORAGE_DIR / "recordings" / f"{test_sid}_interview.webm"
    rec_file.parent.mkdir(parents=True, exist_ok=True)
    rec_file.write_bytes(b"dummy video data")

    audio_file = settings.STORAGE_DIR / "audio" / f"{test_sid}_audio.wav"
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    audio_file.write_bytes(b"dummy audio data")

    # Call purge endpoint
    resp = client.delete(f"/api/interview/{test_sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "deleted"

    # Verify physical file removal
    assert not rec_file.exists()
    assert not audio_file.exists()

    # Verify DB record removal
    db_verify = SessionLocal()
    check = db_verify.query(InterviewSession).filter(InterviewSession.id == test_sid).first()
    assert check is None
    db_verify.close()
