"""Tests for resume parsing, fit scoring, and API endpoints."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.resume_service import resume_service

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

client = TestClient(app)


def test_get_jobs():
    """Verify GET /api/jobs returns seeded jobs."""
    response = client.get("/api/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) >= 12
    job_ids = {j["id"] for j in jobs}
    assert "job_sec_analyst" in job_ids
    assert "job_ml_engineer" in job_ids


def test_search_jobs_trie():
    """Verify Trie-based search on job titles and skills."""
    # Prefix "sec" -> Security Analyst, Network Systems & Security
    res = client.get("/api/jobs/search?q=sec")
    assert res.status_code == 200
    results = res.json()
    assert len(results) >= 1
    titles = [j["title"].lower() for j in results]
    assert any("security" in t for t in titles)

    # Prefix "cloud"
    res_cloud = client.get("/api/jobs/search?q=cloud")
    assert res_cloud.status_code == 200
    assert len(res_cloud.json()) >= 1


def test_parse_sample_pdf_resume():
    """Verify parsing a PDF resume extracted text, skills, and experience."""
    pdf_path = FIXTURES_DIR / "resume_senior_sec_analyst.pdf"
    assert pdf_path.exists(), f"Fixture {pdf_path} must exist"

    file_bytes = pdf_path.read_bytes()
    parsed = resume_service.parse_resume(file_bytes, pdf_path.name)

    assert "Alex Vance" in parsed["candidate_name"]
    assert "Network Security & Cryptography" in parsed["skills"]
    assert parsed["experience_years"] >= 4.0
    assert parsed["education"]["degree"] in ["Master", "Bachelor"]


def test_parse_sample_docx_resume():
    """Verify parsing a DOCX resume."""
    docx_path = FIXTURES_DIR / "resume_cloud_devops_lead.docx"
    assert docx_path.exists(), f"Fixture {docx_path} must exist"

    file_bytes = docx_path.read_bytes()
    parsed = resume_service.parse_resume(file_bytes, docx_path.name)

    assert "Marcus Brody" in parsed["candidate_name"]
    assert any(s in parsed["skills"] for s in ["AWS", "Docker", "Kubernetes"])
    assert parsed["experience_years"] >= 5.0


def test_upload_matching_resume_passes():
    """Verify uploading a matching resume for Security Analyst yields PASSED status."""
    pdf_path = FIXTURES_DIR / "resume_senior_sec_analyst.pdf"
    with open(pdf_path, "rb") as f:
        res = client.post(
            "/api/resume/upload",
            data={"job_id": "job_sec_analyst"},
            files={"file": (pdf_path.name, f, "application/pdf")},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"].startswith("sess_")
    assert data["screening"]["status"] == "PASSED"
    assert data["screening"]["fit_score"] >= 0.65
    assert len(data["screening"]["missing_required_skills"]) == 0


def test_upload_unqualified_resume_rejected():
    """Verify uploading an unqualified resume yields REJECTED status with reasons."""
    pdf_path = FIXTURES_DIR / "resume_mismatched_unqualified.pdf"
    with open(pdf_path, "rb") as f:
        res = client.post(
            "/api/resume/upload",
            data={"job_id": "job_sec_analyst"},
            files={"file": (pdf_path.name, f, "application/pdf")},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"].startswith("sess_")
    assert data["screening"]["status"] == "REJECTED"
    assert len(data["screening"]["reasons"]) > 0
    assert any("Missing required skills" in r for r in data["screening"]["reasons"])


def test_screen_endpoint_with_resume_field_and_custom_name():
    """Verify /api/resume/screen supports 'resume' form field and custom candidate_name."""
    pdf_path = FIXTURES_DIR / "resume_senior_sec_analyst.pdf"
    with open(pdf_path, "rb") as f:
        res = client.post(
            "/api/resume/screen",
            data={"job_id": "job_sec_analyst", "candidate_name": "Sarthak Bhosale"},
            files={"resume": (pdf_path.name, f, "application/pdf")},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"].startswith("sess_")
    assert data["candidate_name"] == "Sarthak Bhosale"
    assert "fit_score" in data
    assert "gaps" in data
    assert "parsed_profile" in data
    assert "skills" in data["parsed_profile"]
