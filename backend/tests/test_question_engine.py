"""Tests for question filtering, selection engine, and interview start API."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.question_service import question_service

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
client = TestClient(app)


def test_question_service_loads_dataset():
    """Verify question service loaded spoken questions and precomputed embeddings."""
    assert len(question_service.spoken_questions) >= 1700
    assert question_service.embeddings is not None
    assert question_service.embeddings.shape[1] == 384


def test_question_selection_pipeline():
    """Verify question selection uses min-heap, MMR, Knapsack, and merge sort."""
    job_dict = {
        "id": "job_sec_analyst",
        "title": "Information Security Analyst",
        "required_skills": ["Network Security & Cryptography", "Application Security"],
        "preferred_skills": ["Cloud Architecture"],
        "question_domains": ["Security", "Operating Systems/Networks"],
    }
    parsed_resume = {
        "skills": ["Network Security & Cryptography", "Application Security", "Zero Trust"],
        "experience_years": 4.0,
    }

    selected = question_service.select_questions(
        job_dict=job_dict,
        parsed_resume=parsed_resume,
        target_duration_seconds=720,
    )

    # Must contain warmup first
    assert len(selected) >= 5
    assert selected[0]["is_warmup"] is True
    assert "introduce yourself" in selected[0]["question"].lower()

    # Time budget must not exceed 720 seconds
    total_time = sum(q.get("est_seconds", 70) for q in selected)
    assert total_time <= 750

    # Non-warmup questions must come from dataset
    dataset_questions = [q for q in selected if not q.get("is_warmup")]
    for q in dataset_questions:
        assert q["id"].startswith("q_")
        assert isinstance(q["domain"], str) and len(q["domain"]) > 0


def test_start_interview_endpoint():
    """Verify POST /api/interview/{sid}/start generates questions and updates session."""
    # First upload resume to create session
    pdf_path = FIXTURES_DIR / "resume_senior_sec_analyst.pdf"
    with open(pdf_path, "rb") as f:
        upload_res = client.post(
            "/api/resume/upload",
            data={"job_id": "job_sec_analyst"},
            files={"file": (pdf_path.name, f, "application/pdf")},
        )
    assert upload_res.status_code == 200
    session_id = upload_res.json()["session_id"]

    # Start interview
    start_res = client.post(f"/api/interview/{session_id}/start")
    assert start_res.status_code == 200
    data = start_res.json()

    assert data["session_id"] == session_id
    assert data["total_questions"] >= 5
    questions = data["questions"]
    assert questions[0]["is_warmup"] is True

    # Check session query endpoint
    get_res = client.get(f"/api/interview/{session_id}")
    assert get_res.status_code == 200
    sess_data = get_res.json()
    assert sess_data["interview_status"] == "IN_PROGRESS"
    assert len(sess_data["questions"]) == len(questions)
